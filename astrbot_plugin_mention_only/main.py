from __future__ import annotations

import asyncio
import random
import time

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Reply
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

from .active_chat import (
    is_active_reply_candidate,
    should_allow_llm_request,
    should_reply,
)
from .affinity import (
    AffinityState,
    advance_affinity,
    affinity_state_key,
    append_relationship_guidance,
    parse_affinity_state,
    relationship_stage,
)
from .chat_style import (
    append_natural_chat_style,
    forget_expired_negative_contexts,
    should_apply_natural_style,
)


@register(
    "mention_only_chat",
    "keita",
    "Gates direct chat and keeps QQ replies conversational and relational.",
    "1.4.0",
)
class MentionOnlyChat(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._affinity_lock = asyncio.Lock()
        self._affinity_cache: dict[str, AffinityState] = {}

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
            if key in self._affinity_cache:
                state = self._affinity_cache[key]
            else:
                raw = await self.get_kv_data(key, {})
                state = parse_affinity_state(raw)
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
