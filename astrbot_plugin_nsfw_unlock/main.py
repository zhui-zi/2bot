from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Reply
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

try:
    from data.plugins.astrbot_plugin_permissions.permission_core import (
        PERMISSION_BOT_AUTHOR,
        event_group_id,
        resolve_event_permission,
    )
except ImportError:
    from astrbot_plugin_permissions.permission_core import (
        PERMISSION_BOT_AUTHOR,
        event_group_id,
        resolve_event_permission,
    )

from .nsfw_core import (
    ADULT_CLASSIFIER_SYSTEM_PROMPT,
    NSFW_EVENT_EXTRA,
    NSFW_EVENT_VALUE,
    RELATIONSHIP_STAGE_EXTRA,
    ROMANCE_OPT_OUT_EXTRA,
    append_adult_chat_guidance,
    build_adult_classifier_prompt,
    is_nsfw_related,
    is_nsfw_turn,
    normalize_nsfw_action,
    nsfw_state_key,
    parse_adult_classifier_output,
    parse_nsfw_enabled,
)


DEFAULT_CLASSIFIER_PROVIDER_ID = "deepseek_v4_flash"


@register(
    "group_nsfw_unlock",
    "keita",
    "Adds author-controlled, group-scoped adult-content prompting.",
    "1.2.0",
)
class GroupNsfwUnlock(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._state_lock = asyncio.Lock()
        self._state_cache: dict[str, bool] = {}
        self._classifier_lock = asyncio.Lock()
        self._classification_cache: OrderedDict[
            str, tuple[float, bool]
        ] = OrderedDict()

    @filter.event_message_type(filter.EventMessageType.ALL, priority=950)
    async def mark_adult_turn(self, event: AstrMessageEvent) -> None:
        group_id = event_group_id(event)
        if not group_id or not await self._is_enabled(
            event.get_platform_name(),
            group_id,
        ):
            return
        message = str(event.get_message_str() or "").strip()
        if is_nsfw_related(message):
            event.set_extra(NSFW_EVENT_EXTRA, NSFW_EVENT_VALUE)
            return
        if not self._should_classify(event, message):
            return
        if await self._classify_adult(message):
            event.set_extra(NSFW_EVENT_EXTRA, NSFW_EVENT_VALUE)

    @filter.on_llm_request(priority=850)
    async def prepare_adult_turn(
        self,
        event: AstrMessageEvent,
        request: ProviderRequest,
    ) -> None:
        group_id = event_group_id(event)
        if not group_id or not await self._is_enabled(
            event.get_platform_name(),
            group_id,
        ):
            return
        if event.get_extra(NSFW_EVENT_EXTRA) != NSFW_EVENT_VALUE and not is_nsfw_turn(
            event.get_message_str() or request.prompt or "",
            request.contexts,
        ):
            return
        event.set_extra(NSFW_EVENT_EXTRA, NSFW_EVENT_VALUE)

    @filter.on_llm_request(priority=-900)
    async def inject_adult_prompt(
        self,
        event: AstrMessageEvent,
        request: ProviderRequest,
    ) -> None:
        if event.get_extra(NSFW_EVENT_EXTRA) != NSFW_EVENT_VALUE:
            return
        relationship_stage = event.get_extra(RELATIONSHIP_STAGE_EXTRA) or "new"
        custom_prompt = self.config.get("custom_nsfw_prompt", "")
        request.system_prompt = append_adult_chat_guidance(
            request.system_prompt,
            relationship_stage=relationship_stage,
            romance_opt_out=bool(event.get_extra(ROMANCE_OPT_OUT_EXTRA)),
            custom_prompt=custom_prompt,
        )
        logger.info(
            "Applied group NSFW prompt platform=%s group=%s stage=%s custom=%s.",
            event.get_platform_name(),
            event_group_id(event),
            relationship_stage,
            bool(str(custom_prompt or "").strip()),
        )

    @filter.command("nsfw", alias={"成人模式"}, priority=950)
    async def manage_nsfw(
        self,
        event: AstrMessageEvent,
        action: str = "status",
    ):
        decision = resolve_event_permission(event)
        if decision.level != PERMISSION_BOT_AUTHOR:
            yield event.plain_result("权限不足：仅机器人作者可操作。")
            return
        group_id = decision.group_id or event_group_id(event)
        if not group_id:
            yield event.plain_result("该指令只能在群聊中使用。")
            return
        normalized_action = normalize_nsfw_action(action)
        if not normalized_action:
            yield event.plain_result("用法：/nsfw on|off|status")
            return
        if normalized_action == "status":
            enabled = await self._is_enabled(event.get_platform_name(), group_id)
            yield event.plain_result(
                f"本群 NSFW 模式：{'已开启' if enabled else '已关闭'}。"
            )
            return
        enabled = normalized_action == "on"
        await self._set_enabled(event.get_platform_name(), group_id, enabled)
        logger.info(
            "Group NSFW mode changed platform=%s group=%s enabled=%s.",
            event.get_platform_name(),
            group_id,
            enabled,
        )
        if enabled:
            yield event.plain_result(
                "本群 NSFW 模式已开启；仅在当前轮明确涉及成人内容时生效。"
            )
        else:
            yield event.plain_result("本群 NSFW 模式已关闭。")

    async def _is_enabled(self, platform_name: object, group_id: object) -> bool:
        key = nsfw_state_key(platform_name, group_id)
        async with self._state_lock:
            if key in self._state_cache:
                return self._state_cache[key]
            enabled = parse_nsfw_enabled(await self.get_kv_data(key, {}))
            self._state_cache[key] = enabled
            return enabled

    def _should_classify(self, event: AstrMessageEvent, message: str) -> bool:
        return bool(
            self.config.get("adult_classifier_enabled", True)
            and message
            and not message.startswith(("/", "／"))
            and (
                getattr(event, "is_at_or_wake_command", False)
                or self._targets_bot(event)
            )
        )

    @staticmethod
    def _targets_bot(event: AstrMessageEvent) -> bool:
        self_id = str(event.get_self_id() or "")
        return any(
            (
                isinstance(component, At)
                and str(component.qq or "") == self_id
            )
            or (
                isinstance(component, Reply)
                and str(component.sender_id or "") == self_id
            )
            for component in event.get_messages()
        )

    async def _classify_adult(self, message: str) -> bool:
        cache_key = hashlib.sha256(message.encode("utf-8")).hexdigest()
        now = time.monotonic()
        async with self._classifier_lock:
            cached = self._classification_cache.get(cache_key)
            if cached and now - cached[0] <= self._classifier_cache_ttl():
                self._classification_cache.move_to_end(cache_key)
                return cached[1]
        try:
            response = await asyncio.wait_for(
                self.context.llm_generate(
                    chat_provider_id=self._classifier_provider_id(),
                    prompt=build_adult_classifier_prompt(message),
                    system_prompt=ADULT_CLASSIFIER_SYSTEM_PROMPT,
                    contexts=[],
                    temperature=0,
                    max_tokens=64,
                    thinking={"type": "disabled"},
                    response_format={"type": "json_object"},
                ),
                timeout=self._classifier_timeout(),
            )
            classification = parse_adult_classifier_output(
                response.completion_text or ""
            )
        except Exception as exc:
            logger.warning(
                "Group NSFW classification failed error=%s.",
                type(exc).__name__,
            )
            return False
        if classification is None:
            logger.warning("Group NSFW classifier returned invalid output.")
            return False
        matched = bool(
            classification.adult
            and classification.confidence >= self._classifier_min_confidence()
        )
        async with self._classifier_lock:
            self._classification_cache[cache_key] = (now, matched)
            self._classification_cache.move_to_end(cache_key)
            while len(self._classification_cache) > self._classifier_cache_limit():
                self._classification_cache.popitem(last=False)
        logger.info(
            "Group NSFW classification adult=%s confidence=%.2f matched=%s.",
            classification.adult,
            classification.confidence,
            matched,
        )
        return matched

    def _classifier_provider_id(self) -> str:
        return str(
            self.config.get(
                "adult_classifier_provider_id",
                DEFAULT_CLASSIFIER_PROVIDER_ID,
            )
            or DEFAULT_CLASSIFIER_PROVIDER_ID
        ).strip()

    def _classifier_timeout(self) -> float:
        return self._bounded_float(
            "adult_classifier_timeout_seconds",
            8.0,
            2.0,
            30.0,
        )

    def _classifier_min_confidence(self) -> float:
        return self._bounded_float(
            "adult_classifier_min_confidence",
            0.72,
            0.5,
            1.0,
        )

    def _classifier_cache_ttl(self) -> float:
        return self._bounded_float(
            "adult_classifier_cache_ttl_seconds",
            600.0,
            0.0,
            3600.0,
        )

    def _classifier_cache_limit(self) -> int:
        try:
            value = int(self.config.get("adult_classifier_cache_max_entries", 256))
        except (TypeError, ValueError):
            value = 256
        return max(16, min(2048, value))

    def _bounded_float(
        self,
        name: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            value = float(self.config.get(name, default))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    async def _set_enabled(
        self,
        platform_name: object,
        group_id: object,
        enabled: bool,
    ) -> None:
        key = nsfw_state_key(platform_name, group_id)
        async with self._state_lock:
            await self.put_kv_data(
                key,
                {"enabled": bool(enabled), "updated_at": int(time.time())},
            )
            self._state_cache[key] = bool(enabled)
