from __future__ import annotations

import asyncio
import time

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
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
    NSFW_EVENT_EXTRA,
    NSFW_EVENT_VALUE,
    append_adult_chat_guidance,
    is_nsfw_related,
    is_nsfw_turn,
    normalize_nsfw_action,
    nsfw_state_key,
    parse_nsfw_enabled,
)


@register(
    "group_nsfw_unlock",
    "keita",
    "Adds author-controlled, group-scoped adult-content prompting.",
    "1.0.0",
)
class GroupNsfwUnlock(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._state_lock = asyncio.Lock()
        self._state_cache: dict[str, bool] = {}

    @filter.event_message_type(filter.EventMessageType.ALL, priority=950)
    async def mark_adult_turn(self, event: AstrMessageEvent) -> None:
        group_id = event_group_id(event)
        if not group_id or not is_nsfw_related(event.get_message_str() or ""):
            return
        if await self._is_enabled(event.get_platform_name(), group_id):
            event.set_extra(NSFW_EVENT_EXTRA, NSFW_EVENT_VALUE)

    @filter.on_llm_request(priority=850)
    async def inject_adult_prompt(
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
        request.system_prompt = append_adult_chat_guidance(request.system_prompt)

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
