from __future__ import annotations

from typing import Any

from astrbot.api.event import AstrMessageEvent, MessageEventResult, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.config.default import VERSION
from astrbot.core.dashboard_assets import get_dashboard_version
from astrbot.core.star import command_management

from .help_text import (
    CommandInfo,
    build_help_text,
    build_source_text,
    build_sponsor_text,
    is_help_request,
)


@register(
    "complete_help",
    "keita",
    "Replaces the built-in help output with concise Chinese command guidance.",
    "1.8.0",
)
class CompleteHelp(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("source", alias={"开源", "源码"})
    async def source(self, event: AstrMessageEvent):
        """Show the public source repository."""
        yield event.plain_result(build_source_text())

    @filter.command("sponsor", alias={"赞助", "爱发电"})
    async def sponsor(self, event: AstrMessageEvent):
        """Show the sponsorship page."""
        yield event.plain_result(build_sponsor_text())

    @filter.on_decorating_result(priority=100)
    async def replace_help_result(self, event: AstrMessageEvent) -> None:
        """Replace the built-in help result after command handling."""
        if (
            not is_help_request(event.get_message_str() or "")
            and event.get_extra("_front_command") != "help"
        ):
            return

        commands = await self._enabled_commands()
        dashboard_version = await get_dashboard_version()
        text = build_help_text(
            f"AstrBot v{VERSION}(WebUI: {dashboard_version})",
            commands,
        )
        event.set_result(MessageEventResult().message(text).use_t2i(False))

    @staticmethod
    async def _enabled_commands() -> list[CommandInfo] | None:
        try:
            records = await command_management.list_commands()
        except BaseException:
            return None

        commands: list[CommandInfo] = []

        def walk(items: list[dict[str, Any]]) -> None:
            for item in items:
                children = item.get("sub_commands")
                if isinstance(children, list):
                    walk(children)
                if not item.get("enabled", True):
                    continue
                if item.get("type") == "sub_command" or item.get("parent_signature"):
                    continue
                original = str(
                    item.get("original_command") or item.get("handler_name") or ""
                ).strip()
                effective = str(item.get("effective_command") or original).strip()
                if original and effective:
                    commands.append(
                        CommandInfo(
                            original=original,
                            effective=effective,
                            description=str(item.get("description") or "").strip(),
                            aliases=tuple(
                                str(alias).strip()
                                for alias in item.get("aliases", [])
                                if str(alias).strip()
                            ),
                        )
                    )

        walk(records)
        return commands or None
