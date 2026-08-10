from __future__ import annotations

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .permission_core import (
    configure_permission_policy,
    current_permission_policy,
    resolve_event_permission,
)


@register(
    "unified_permissions",
    "keita",
    "Provides one permission hierarchy for all bot features.",
    "1.0.0",
)
class UnifiedPermissions(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        configure_permission_policy(
            bot_author_ids=config.get("bot_author_ids", []),
            group_manager_overrides=config.get("group_manager_overrides", []),
        )

    @filter.on_astrbot_loaded()
    async def audit_permission_policy(self) -> None:
        policy = current_permission_policy()
        logger.info(
            "Unified permissions loaded: authors=%s group overrides=%s.",
            len(policy.bot_author_ids),
            len(policy.group_manager_overrides),
        )

    @filter.command("permission", alias={"权限"})
    async def permission_status(self, event: AstrMessageEvent):
        """Show the caller's effective permission level."""
        decision = resolve_event_permission(event)
        yield event.plain_result(
            f"当前权限：{decision.label}\n"
            "层级：机器人作者 > AstrBot 管理员 > 当前群群主/管理员 > 普通成员"
        )
