from __future__ import annotations

import asyncio
import random
import time
from contextlib import suppress
from datetime import datetime
from zoneinfo import ZoneInfo

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Plain, Reply
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.message.message_event_result import MessageChain

from .active_chat import (
    is_active_reply_candidate,
    should_allow_llm_request,
    should_quote_group_reply,
    should_reply,
)
from .affinity import (
    AffinityState,
    advance_affinity,
    affinity_state_key,
    append_relationship_guidance,
    can_manage_affinity,
    parse_affinity_state,
    private_state_probe_kind,
    relationship_stage,
)
from .chat_style import (
    append_natural_chat_style,
    compact_casual_reply,
    forget_expired_negative_contexts,
    is_casual_chat_message,
    should_apply_natural_style,
)


@register(
    "mention_only_chat",
    "keita",
    "Gates direct chat and keeps QQ replies conversational and relational.",
    "1.6.0",
)
class MentionOnlyChat(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._affinity_lock = asyncio.Lock()
        self._affinity_cache: dict[str, AffinityState] = {}

    @filter.event_message_type(filter.EventMessageType.ALL, priority=900)
    async def protect_private_relationship_state(self, event: AstrMessageEvent):
        platform_name = str(event.get_platform_name() or "").strip().casefold()
        if platform_name not in {"qq_official", "aiocqhttp"}:
            return
        message = str(event.get_message_str() or "").strip()
        if message.casefold().startswith(("/affinity", "/好感管理")):
            return
        probe_kind = private_state_probe_kind(message)
        if not probe_kind:
            return
        if not (bool(event.is_private_chat()) or self._targets_bot(event)):
            return
        if self._can_manage_affinity(event):
            yield event.plain_result("管理员请使用 /affinity status，并回复或 @ 目标用户。")
        elif probe_kind == "affinity":
            yield event.plain_result("哪有这种数值。相处得怎么样，你自己感觉不出来？")
        else:
            yield event.plain_result("少套我的话，正常聊。")
        event.stop_event()

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE, priority=-100)
    async def maybe_join_group_chat(self, event: AstrMessageEvent):
        message = str(event.get_message_str() or "")
        explicit_trigger = bool(event.is_at_or_wake_command) or self._targets_bot(event)
        if not is_active_reply_candidate(
            platform_name=str(event.get_platform_name() or ""),
            is_group_chat=bool(event.get_group_id()),
            is_explicit_trigger=explicit_trigger,
            sender_id=str(event.get_sender_id()),
            self_id=str(event.get_self_id()),
            message=message,
        ):
            return

        percent = self.config.get("active_reply_percent", 5)
        if not should_reply(percent, random.random()):
            return

        provider = self.context.get_using_provider(event.unified_msg_origin)
        if not provider:
            logger.warning("Active group reply skipped because no LLM provider is available.")
            return

        conversation_manager = self.context.conversation_manager
        conversation_id = await conversation_manager.get_curr_conversation_id(
            event.unified_msg_origin,
        )
        if not conversation_id:
            conversation_id = await conversation_manager.new_conversation(
                event.unified_msg_origin,
                platform_id=event.get_platform_id(),
            )
        conversation = await conversation_manager.get_conversation(
            event.unified_msg_origin,
            conversation_id,
        )
        if not conversation:
            logger.warning("Active group reply skipped because no conversation is available.")
            return

        event.set_extra("_mention_only_llm_allow", "active_reply")
        logger.info(
            "Active group reply triggered for platform=%s group=%s probability=%s%%.",
            event.get_platform_name(),
            event.get_group_id(),
            percent,
        )
        yield event.request_llm(prompt=message, conversation=conversation)

    @filter.on_llm_request()
    async def require_direct_mention(
        self,
        event: AstrMessageEvent,
        request: ProviderRequest,
    ) -> None:
        if not should_allow_llm_request(
            platform_name=str(event.get_platform_name() or ""),
            is_private_chat=bool(event.is_private_chat()),
            targets_bot=self._targets_bot(event),
            allow_reason=str(event.get_extra("_mention_only_llm_allow") or ""),
        ):
            event.stop_event()
            return

        platform_name = event.get_platform_name()
        if should_apply_natural_style(
            platform_name,
            self.config.get("enforce_short_casual_replies", True),
        ):
            casual = is_casual_chat_message(
                event.get_message_str() or request.prompt or "",
                allow_reason=event.get_extra("_mention_only_llm_allow") or "",
            )
            event.set_extra("_mention_only_compact_casual", "1" if casual else "0")

        if should_apply_natural_style(
            platform_name,
            self.config.get("hidden_affinity_enabled", True),
        ):
            state = await self._relationship_state(event)
            if state is not None:
                request.system_prompt = append_relationship_guidance(
                    request.system_prompt,
                    relationship_stage(
                        state,
                        romance_enabled=bool(
                            self.config.get("hidden_romance_enabled", True)
                        ),
                    ),
                )

        if should_apply_natural_style(
            platform_name,
            self.config.get("forget_expired_negative_context", True),
        ):
            request.contexts = forget_expired_negative_contexts(
                request.contexts,
                keep_recent=self.config.get("recent_negative_context_messages", 4),
            )

        if should_apply_natural_style(
            platform_name,
            self.config.get("natural_chat_style", True),
        ):
            request.system_prompt = append_natural_chat_style(request.system_prompt)

    @filter.on_llm_response(priority=200)
    async def enforce_casual_reply_length(
        self,
        event: AstrMessageEvent,
        response: LLMResponse,
    ) -> None:
        if event.get_extra("_mention_only_compact_casual") != "1":
            return
        compacted = compact_casual_reply(
            response.completion_text or "",
            max_chars=self.config.get("casual_reply_max_chars", 42),
        )
        if compacted and compacted != response.completion_text:
            response.completion_text = compacted

    @filter.on_llm_response(priority=-100)
    async def quote_group_reply_target(
        self,
        event: AstrMessageEvent,
        response: LLMResponse,
    ) -> None:
        message_id = str(getattr(event.message_obj, "message_id", "") or "").strip()
        if not self.config.get("quote_group_replies", True):
            return
        if not should_quote_group_reply(
            platform_name=event.get_platform_name(),
            is_group_chat=bool(event.get_group_id()),
            message_id=message_id,
        ):
            return
        reply = Reply(
            id=message_id,
            sender_id=str(event.get_sender_id() or ""),
            sender_nickname=self._sender_name(event),
        )
        if response.result_chain:
            if not any(
                isinstance(component, Reply)
                for component in response.result_chain.chain
            ):
                response.result_chain.chain.insert(0, reply)
            return
        text = str(response.completion_text or "")
        response.result_chain = MessageChain([reply, Plain(text)])

    @filter.command("affinity", alias={"好感管理"}, priority=900)
    async def affinity_admin(
        self,
        event: AstrMessageEvent,
        action: str = "status",
        target_id: str = "",
    ):
        if not self._can_manage_affinity(event):
            yield event.plain_result("无权限。")
            return
        if str(action or "status").casefold().strip() not in {
            "status", "query", "状态", "查询",
        }:
            yield event.plain_result(
                "用法：/affinity status [用户ID]，也可以回复或 @ 目标用户。"
            )
            return
        target = str(target_id or "").strip() or self._affinity_target(event)
        if not target:
            target = str(event.get_sender_id() or "").strip()
        state = await self._load_affinity_state(event.get_platform_name(), target)
        stage = relationship_stage(
            state,
            romance_enabled=bool(self.config.get("hidden_romance_enabled", True)),
        )
        stage_name = {
            "new": "初识",
            "familiar": "熟悉",
            "trusted": "信任",
            "close": "亲近",
            "romantic": "恋爱",
            "devoted": "深度恋爱",
        }.get(stage, stage)
        last_seen = "从未互动"
        if state.last_seen_at:
            last_seen = datetime.fromtimestamp(
                state.last_seen_at,
                ZoneInfo("Asia/Shanghai"),
            ).strftime("%Y-%m-%d %H:%M")
        yield event.plain_result(
            f"用户：{target}\n"
            f"好感：{state.score}/100（{stage_name}）\n"
            f"有效互动：{state.positive_interactions}\n"
            f"恋爱信号日：{state.romance_signals}\n"
            f"拒绝恋爱化：{'是' if state.romance_opt_out else '否'}\n"
            f"最近互动：{last_seen}"
        )

    async def _relationship_state(
        self,
        event: AstrMessageEvent,
    ) -> AffinityState | None:
        sender_id = str(event.get_sender_id() or "").strip()
        if not sender_id or sender_id == str(event.get_self_id() or "").strip():
            return None
        key = affinity_state_key(event.get_platform_name(), sender_id)
        direct_interaction = bool(event.is_private_chat()) or self._targets_bot(event)
        async with self._affinity_lock:
            state = await self._load_affinity_state_locked(key)
            updated = state
            if direct_interaction:
                updated = advance_affinity(
                    state,
                    event.get_message_str() or "",
                    now=time.time(),
                    min_award_minutes=self.config.get(
                        "affinity_min_award_minutes",
                        20,
                    ),
                    daily_gain_cap=self.config.get("affinity_daily_gain_cap", 6),
                    inactivity_grace_days=self.config.get(
                        "affinity_inactivity_grace_days",
                        45,
                    ),
                )
            if updated != state:
                await self.put_kv_data(key, updated.to_dict())
            self._affinity_cache[key] = updated
            return updated

    async def _load_affinity_state(
        self,
        platform_name: object,
        sender_id: object,
    ) -> AffinityState:
        key = affinity_state_key(platform_name, sender_id)
        async with self._affinity_lock:
            return await self._load_affinity_state_locked(key)

    async def _load_affinity_state_locked(self, key: str) -> AffinityState:
        if key in self._affinity_cache:
            return self._affinity_cache[key]
        raw = await self.get_kv_data(key, {})
        state = parse_affinity_state(raw)
        self._affinity_cache[key] = state
        return state

    def _can_manage_affinity(self, event: AstrMessageEvent) -> bool:
        is_admin = False
        with suppress(Exception):
            is_admin = bool(event.is_admin())
        return can_manage_affinity(
            event.get_sender_id(),
            is_admin=is_admin,
            manager_ids=self.config.get("affinity_manager_ids", []),
        )

    @staticmethod
    def _affinity_target(event: AstrMessageEvent) -> str:
        self_id = str(event.get_self_id() or "").strip()
        for component in event.get_messages():
            if isinstance(component, Reply):
                sender_id = str(component.sender_id or "").strip()
                if sender_id and sender_id != self_id:
                    return sender_id
            elif isinstance(component, At):
                sender_id = str(component.qq or "").strip()
                if sender_id and sender_id not in {"all", self_id}:
                    return sender_id
        return ""

    @staticmethod
    def _sender_name(event: AstrMessageEvent) -> str:
        getter = getattr(event, "get_sender_name", None)
        if callable(getter):
            with suppress(Exception):
                name = str(getter() or "").strip()
                if name:
                    return name[:50]
        return "群成员"

    @staticmethod
    def _targets_bot(event: AstrMessageEvent) -> bool:
        self_id = str(event.get_self_id())
        return any(
            (
                isinstance(component, At)
                and str(component.qq) == self_id
            )
            or (
                isinstance(component, Reply)
                and str(component.sender_id) == self_id
            )
            for component in event.get_messages()
        )
