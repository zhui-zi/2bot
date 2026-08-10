from __future__ import annotations

import asyncio
import hashlib
import inspect
import time
from collections import OrderedDict
from collections.abc import AsyncGenerator
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Reply
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.platform.astr_message_event import AstrMessageEvent as CoreEvent
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.permission import PermissionTypeFilter
from astrbot.core.star.session_plugin_manager import SessionPluginManager
from astrbot.core.star.star import star_map
from astrbot.core.star.star_handler import EventType, StarHandlerMetadata, star_handlers_registry

from .front_core import (
    CLASSIFIER_SYSTEM_PROMPT,
    ROUTED_COMMANDS,
    SECURITY_BOUNDARY,
    SECURITY_REPLY_FALLBACKS,
    SECURITY_REPLY_SYSTEM_PROMPT,
    SYSTEM_COMMAND_REPLY,
    CommandIntent,
    FrontClassification,
    build_classifier_prompt,
    build_security_reply_prompt,
    classification_intent,
    clean_security_reply,
    is_harassing_message,
    is_natural_system_request,
    is_pvp_gameplay_question,
    is_prompt_injection,
    match_natural_command,
    match_reply_correction,
    parse_classifier_output,
    protect_housing_intent,
)


DEFAULT_FLASH_PROVIDER_ID = "deepseek_v4_flash"


@register(
    "unified_front_guard",
    "keita",
    "Routes user features and protects model requests through a Flash front layer.",
    "1.3.6",
)
class UnifiedFrontGuard(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._classification_cache: OrderedDict[
            str, tuple[float, FrontClassification]
        ] = OrderedDict()
        self._cache_lock = asyncio.Lock()

    @filter.on_astrbot_loaded()
    async def audit_front_layer(self) -> None:
        available: set[str] = set()
        for handler in star_handlers_registry.get_handlers_by_event_type(
            EventType.AdapterMessageEvent,
        ):
            if not handler.enabled:
                continue
            for event_filter in handler.event_filters:
                if isinstance(event_filter, CommandFilter):
                    available.add(
                        getattr(
                            event_filter,
                            "_original_command_name",
                            event_filter.command_name,
                        )
                    )
        missing = sorted(ROUTED_COMMANDS.difference(available))
        provider_id = self._provider_id()
        logger.info(
            "Unified front guard resolved %s/%s commands; Flash provider=%s.",
            len(ROUTED_COMMANDS) - len(missing),
            len(ROUTED_COMMANDS),
            provider_id,
        )
        if missing:
            logger.warning("Front command targets unavailable: %s", ", ".join(missing))
        if self._classifier_enabled() and not self.context.get_provider_by_id(provider_id):
            logger.warning("Front Flash provider is unavailable: %s", provider_id)

    @filter.event_message_type(filter.EventMessageType.ALL, priority=900)
    async def process_front_layer(self, event: AstrMessageEvent):
        message = str(event.get_message_str() or "").strip()
        if not message:
            return
        is_direct = bool(event.is_private_chat() or event.is_at_or_wake_command)
        if not is_direct:
            return

        if is_harassing_message(message):
            yield event.plain_result(
                await self._generate_security_reply("harassment", message)
            )
            event.stop_event()
            return
        if is_prompt_injection(message):
            yield event.plain_result(
                await self._generate_security_reply("prompt_injection", message)
            )
            event.stop_event()
            return
        if self._has_explicit_command(event):
            event.set_extra("_front_guard_checked", "explicit_command")
            return
        if is_natural_system_request(message):
            yield event.plain_result(SYSTEM_COMMAND_REPLY)
            event.stop_event()
            return
        if is_pvp_gameplay_question(message):
            event.set_extra("_front_guard_checked", "local")
            return

        intent = match_reply_correction(message, self._quoted_bot_message(event))
        if intent is None:
            intent = match_natural_command(message)
        classification: FrontClassification | None = None
        if intent is None and self._classifier_enabled():
            classification = await self._classify(message)
            block_reply = await self._classified_block_reply(classification, message)
            if block_reply:
                yield event.plain_result(block_reply)
                event.stop_event()
                return
            intent = classification_intent(
                classification,
                self._command_confidence(),
            )

        intent = protect_housing_intent(message, intent)

        event.set_extra("_front_guard_checked", "flash" if classification else "local")
        if intent is None:
            return
        async for result in self._dispatch(event, intent):
            yield result

    @staticmethod
    def _quoted_bot_message(event: AstrMessageEvent) -> str:
        self_id = str(event.get_self_id() or "")
        for component in event.get_messages():
            if not isinstance(component, Reply):
                continue
            sender_id = str(getattr(component, "sender_id", "") or "")
            if self_id and sender_id and sender_id != self_id:
                continue
            return str(getattr(component, "message_str", "") or "")
        return ""

    @filter.on_llm_request(priority=900)
    async def protect_llm_request(
        self,
        event: AstrMessageEvent,
        request: ProviderRequest,
    ) -> None:
        message = str(event.get_message_str() or request.prompt or "")
        if is_harassing_message(message):
            event.set_result(
                event.plain_result(
                    await self._generate_security_reply("harassment", message)
                )
            )
            event.stop_event()
            return
        if is_prompt_injection(message):
            event.set_result(
                event.plain_result(
                    await self._generate_security_reply("prompt_injection", message)
                )
            )
            event.stop_event()
            return
        system_prompt = str(request.system_prompt or "")
        if "[Front security boundary]" not in system_prompt:
            request.system_prompt = system_prompt + SECURITY_BOUNDARY

    async def _classified_block_reply(
        self,
        classification: FrontClassification | None,
        message: str,
    ) -> str:
        if (
            classification is None
            or classification.confidence < self._security_confidence()
        ):
            return ""
        if classification.kind == "harassment":
            return await self._generate_security_reply("harassment", message)
        if classification.kind == "prompt_injection":
            return await self._generate_security_reply("prompt_injection", message)
        if classification.kind == "system_request":
            return SYSTEM_COMMAND_REPLY
        return ""

    async def _generate_security_reply(self, kind: str, message: str) -> str:
        fallback = SECURITY_REPLY_FALLBACKS[kind]
        try:
            response = await asyncio.wait_for(
                self.context.llm_generate(
                    chat_provider_id=self._provider_id(),
                    prompt=build_security_reply_prompt(kind, message),
                    system_prompt=SECURITY_REPLY_SYSTEM_PROMPT,
                    contexts=[],
                    temperature=self._security_reply_temperature(),
                    max_tokens=self._security_reply_max_tokens(),
                    thinking={"type": "disabled"},
                ),
                timeout=self._security_reply_timeout(),
            )
            reply = clean_security_reply(response.completion_text or "")
            if reply:
                logger.info("Front Flash generated security reply kind=%s.", kind)
                return reply
            logger.warning("Front Flash returned an empty security reply kind=%s.", kind)
        except Exception as exc:
            logger.warning(
                "Front Flash security reply failed kind=%s error=%s.",
                kind,
                type(exc).__name__,
            )
        return fallback

    async def _classify(self, message: str) -> FrontClassification | None:
        cache_key = hashlib.sha256(message.encode("utf-8")).hexdigest()
        now = time.monotonic()
        async with self._cache_lock:
            cached = self._classification_cache.get(cache_key)
            if cached and now - cached[0] <= self._cache_ttl():
                self._classification_cache.move_to_end(cache_key)
                return cached[1]

        try:
            response = await asyncio.wait_for(
                self.context.llm_generate(
                    chat_provider_id=self._provider_id(),
                    prompt=build_classifier_prompt(message),
                    system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                    contexts=[],
                    temperature=0,
                    max_tokens=180,
                    thinking={"type": "disabled"},
                    response_format={"type": "json_object"},
                ),
                timeout=self._classifier_timeout(),
            )
            classification = parse_classifier_output(response.completion_text or "")
        except Exception as exc:
            logger.warning("Front Flash classification failed: %s", type(exc).__name__)
            return None
        if classification is None:
            logger.warning("Front Flash classifier returned invalid output.")
            return None

        async with self._cache_lock:
            self._classification_cache[cache_key] = (now, classification)
            self._classification_cache.move_to_end(cache_key)
            while len(self._classification_cache) > self._cache_limit():
                self._classification_cache.popitem(last=False)
        logger.info(
            "Front Flash classification kind=%s command=%s confidence=%.2f.",
            classification.kind,
            classification.command or "-",
            classification.confidence,
        )
        return classification

    async def _dispatch(
        self,
        event: AstrMessageEvent,
        intent: CommandIntent,
    ) -> AsyncGenerator[Any, None]:
        resolved = await self._resolve_handler(event, intent)
        if resolved is None:
            yield event.plain_result("这个功能当前未启用，请发送 /help 查看可用功能。")
            event.stop_event()
            return

        handler, command_filter = resolved
        config = self.context.get_config(event.unified_msg_origin)
        if not command_filter.custom_filter_ok(event, config):
            return
        for event_filter in handler.event_filters:
            if isinstance(event_filter, CommandFilter):
                continue
            if not event_filter.filter(event, config):
                if isinstance(event_filter, PermissionTypeFilter):
                    yield event.plain_result("你没有权限使用这个功能。")
                    event.stop_event()
                return

        try:
            params = command_filter.validate_and_convert_params(
                intent.arguments.split() if intent.arguments else [],
                command_filter.handler_params,
            )
        except ValueError:
            yield event.plain_result("没有识别到完整参数，请发送 /help 查看用法。")
            event.stop_event()
            return

        original_message = event.message_str
        raw_command = getattr(
            command_filter,
            "_original_command_name",
            command_filter.command_name,
        )
        event.message_str = f"{raw_command} {intent.arguments}".strip()
        event.set_extra("_front_command", intent.command)
        logger.info(
            "Front command matched command=%s platform=%s group=%s.",
            intent.command,
            event.get_platform_name(),
            event.get_group_id(),
        )
        try:
            async for result in self._invoke(handler, event, params):
                yield result
        except Exception:
            logger.exception("Front command dispatch failed for %s.", intent.command)
            yield event.plain_result("这个功能暂时执行失败，请稍后重试。")
        finally:
            event.message_str = original_message
        event.stop_event()

    async def _resolve_handler(
        self,
        event: AstrMessageEvent,
        intent: CommandIntent,
    ) -> tuple[StarHandlerMetadata, CommandFilter] | None:
        handlers = star_handlers_registry.get_handlers_by_event_type(
            EventType.AdapterMessageEvent,
            plugins_name=event.plugins_name,
        )
        for handler in handlers:
            if not handler.enabled:
                continue
            plugin = star_map.get(handler.handler_module_path)
            if not plugin or not plugin.activated or not plugin.name:
                continue
            if not await SessionPluginManager.is_plugin_enabled_for_session(
                event.unified_msg_origin,
                plugin.name,
            ):
                continue
            for event_filter in handler.event_filters:
                if not isinstance(event_filter, CommandFilter):
                    continue
                original = getattr(
                    event_filter,
                    "_original_command_name",
                    event_filter.command_name,
                )
                if original == intent.command:
                    return handler, event_filter
        return None

    @staticmethod
    def _has_explicit_command(event: AstrMessageEvent) -> bool:
        for handler in event.get_extra("activated_handlers", []) or []:
            if any(
                isinstance(event_filter, CommandFilter)
                for event_filter in handler.event_filters
            ):
                return True
        return False

    @staticmethod
    async def _invoke(
        handler: StarHandlerMetadata,
        event: CoreEvent,
        params: dict[str, Any],
    ) -> AsyncGenerator[Any, None]:
        response = handler.handler(event, **params)
        if inspect.isasyncgen(response):
            async for item in response:
                yield item
            return
        if inspect.isawaitable(response):
            item = await response
            if item is not None:
                yield item

    def _provider_id(self) -> str:
        return str(
            self.config.get("flash_provider_id", DEFAULT_FLASH_PROVIDER_ID)
            or DEFAULT_FLASH_PROVIDER_ID
        ).strip()

    def _classifier_enabled(self) -> bool:
        return bool(self.config.get("classifier_enabled", True))

    def _classifier_timeout(self) -> float:
        return self._bounded_float("classifier_timeout_seconds", 8.0, 2.0, 30.0)

    def _command_confidence(self) -> float:
        return self._bounded_float("command_min_confidence", 0.78, 0.5, 1.0)

    def _security_confidence(self) -> float:
        return self._bounded_float("security_min_confidence", 0.88, 0.5, 1.0)

    def _security_reply_timeout(self) -> float:
        return self._bounded_float("security_reply_timeout_seconds", 8.0, 2.0, 30.0)

    def _security_reply_temperature(self) -> float:
        return self._bounded_float("security_reply_temperature", 0.9, 0.0, 1.5)

    def _security_reply_max_tokens(self) -> int:
        try:
            value = int(self.config.get("security_reply_max_tokens", 96))
        except (TypeError, ValueError):
            value = 96
        return max(32, min(256, value))

    def _cache_ttl(self) -> float:
        return self._bounded_float("cache_ttl_seconds", 300.0, 0.0, 3600.0)

    def _cache_limit(self) -> int:
        try:
            value = int(self.config.get("cache_max_entries", 256))
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
