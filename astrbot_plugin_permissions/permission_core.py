from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Iterable


GROUP_MANAGER_ROLES = frozenset(
    {
        "admin",
        "administrator",
        "group_admin",
        "group_owner",
        "owner",
        "群主",
        "管理员",
    }
)


class PermissionLevel(IntEnum):
    MEMBER = 0
    GROUP_MANAGER = 10
    ASTRBOT_ADMIN = 20
    BOT_AUTHOR = 30


PERMISSION_MEMBER = PermissionLevel.MEMBER
PERMISSION_GROUP_MANAGER = PermissionLevel.GROUP_MANAGER
PERMISSION_ASTRBOT_ADMIN = PermissionLevel.ASTRBOT_ADMIN
PERMISSION_BOT_AUTHOR = PermissionLevel.BOT_AUTHOR


@dataclass(frozen=True)
class PermissionDecision:
    level: PermissionLevel
    source: str
    sender_id: str
    group_id: str = ""

    @property
    def label(self) -> str:
        return {
            PermissionLevel.BOT_AUTHOR: "机器人作者",
            PermissionLevel.ASTRBOT_ADMIN: "AstrBot 管理员",
            PermissionLevel.GROUP_MANAGER: "当前群群主/管理员",
            PermissionLevel.MEMBER: "普通成员",
        }[self.level]


@dataclass(frozen=True)
class PermissionPolicy:
    bot_author_ids: frozenset[str] = frozenset()
    group_manager_overrides: frozenset[tuple[str, str]] = frozenset()


_POLICY = PermissionPolicy()


def configure_permission_policy(
    *,
    bot_author_ids: object = (),
    group_manager_overrides: object = (),
) -> PermissionPolicy:
    global _POLICY
    _POLICY = PermissionPolicy(
        bot_author_ids=_normalized_ids(bot_author_ids),
        group_manager_overrides=_parse_group_overrides(group_manager_overrides),
    )
    return _POLICY


def current_permission_policy() -> PermissionPolicy:
    return _POLICY


def resolve_permission(
    sender_id: object,
    *,
    is_astrbot_admin: object = False,
    bot_author_ids: Iterable[object] = (),
    is_group_chat: object = False,
    group_id: object = "",
    platform_roles: Iterable[object] = (),
    group_manager_overrides: Iterable[tuple[object, object]] = (),
) -> PermissionDecision:
    sender = str(sender_id or "").strip()
    group = str(group_id or "").strip()
    authors = _normalized_ids(bot_author_ids)
    if sender and sender in authors:
        return PermissionDecision(
            PermissionLevel.BOT_AUTHOR,
            "bot_author_ids",
            sender,
            group,
        )
    if bool(is_astrbot_admin):
        return PermissionDecision(
            PermissionLevel.ASTRBOT_ADMIN,
            "astrbot_admin",
            sender,
            group,
        )
    if bool(is_group_chat) and group:
        roles = {
            str(role or "").casefold().strip()
            for role in platform_roles
            if str(role or "").strip()
        }
        overrides = {
            (str(item_group or "").strip(), str(item_sender or "").strip())
            for item_group, item_sender in group_manager_overrides
        }
        if roles & GROUP_MANAGER_ROLES:
            return PermissionDecision(
                PermissionLevel.GROUP_MANAGER,
                "platform_group_role",
                sender,
                group,
            )
        if sender and (group, sender) in overrides:
            return PermissionDecision(
                PermissionLevel.GROUP_MANAGER,
                "group_manager_overrides",
                sender,
                group,
            )
    return PermissionDecision(PermissionLevel.MEMBER, "member", sender, group)


def resolve_event_permission(event: Any) -> PermissionDecision:
    policy = current_permission_policy()
    raw = event_raw_data(event)
    group_id = event_group_id(event, raw)
    is_group_chat = bool(group_id)
    if not is_group_chat:
        getter = getattr(event, "is_private_chat", None)
        if callable(getter):
            try:
                is_group_chat = not bool(getter()) and _raw_is_group(raw)
            except Exception:
                is_group_chat = _raw_is_group(raw)
    is_admin = False
    getter = getattr(event, "is_admin", None)
    if callable(getter):
        try:
            is_admin = bool(getter())
        except Exception:
            is_admin = False
    sender_getter = getattr(event, "get_sender_id", None)
    sender_id = sender_getter() if callable(sender_getter) else ""
    return resolve_permission(
        sender_id,
        is_astrbot_admin=is_admin,
        bot_author_ids=policy.bot_author_ids,
        is_group_chat=is_group_chat,
        group_id=group_id,
        platform_roles=extract_platform_roles(raw),
        group_manager_overrides=policy.group_manager_overrides,
    )


def permission_management_scope(decision: PermissionDecision) -> str:
    if decision.level >= PermissionLevel.ASTRBOT_ADMIN:
        return "global"
    if decision.level >= PermissionLevel.GROUP_MANAGER and decision.group_id:
        return "group"
    return "none"


def extract_platform_roles(raw: object) -> set[str]:
    if not isinstance(raw, dict):
        return set()
    values: list[object] = [raw.get("role"), raw.get("roles")]
    for container_name in ("author", "member", "sender"):
        container = raw.get(container_name)
        if isinstance(container, dict):
            values.extend((container.get("role"), container.get("roles")))
    roles: set[str] = set()
    for value in values:
        if isinstance(value, (list, tuple, set, frozenset)):
            roles.update(str(item or "").casefold().strip() for item in value)
        elif value is not None:
            roles.add(str(value).casefold().strip())
    roles.discard("")
    return roles


def event_raw_data(event: Any) -> object:
    message_obj = getattr(event, "message_obj", None)
    raw_message = getattr(message_obj, "raw_message", None)
    return getattr(raw_message, "raw_data", raw_message)


def event_group_id(event: Any, raw: object | None = None) -> str:
    getter = getattr(event, "get_group_id", None)
    if callable(getter):
        try:
            group_id = str(getter() or "").strip()
            if group_id:
                return group_id
        except Exception:
            pass
    if raw is None:
        raw = event_raw_data(event)
    if isinstance(raw, dict):
        for key in ("group_openid", "group_id", "group_uuid"):
            value = str(raw.get(key) or "").strip()
            if value:
                return value
    return ""


def _raw_is_group(raw: object) -> bool:
    if not isinstance(raw, dict):
        return False
    return bool(
        raw.get("group_openid")
        or raw.get("group_id")
        or str(raw.get("message_type") or "").casefold() == "group"
    )


def _normalized_ids(values: object) -> frozenset[str]:
    if not isinstance(values, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(
        normalized
        for value in values
        if (normalized := str(value or "").strip())
    )


def _parse_group_overrides(values: object) -> frozenset[tuple[str, str]]:
    if not isinstance(values, (list, tuple, set, frozenset)):
        return frozenset()
    overrides: set[tuple[str, str]] = set()
    for value in values:
        text = str(value or "").strip()
        separator = "|" if "|" in text else ":"
        if separator not in text:
            continue
        group_id, sender_id = (part.strip() for part in text.split(separator, 1))
        if group_id and sender_id:
            overrides.add((group_id, sender_id))
    return frozenset(overrides)
