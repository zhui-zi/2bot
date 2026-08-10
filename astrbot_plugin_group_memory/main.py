from __future__ import annotations

import asyncio
import hashlib
import time
from contextlib import suppress
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Reply
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.message import TextPart

from .memory_core import (
    MemoryRecord,
    MemberRelation,
    append_record,
    filter_durable_records,
    find_nickname_relations,
    is_allowlisted_group,
    looks_sensitive,
    looks_transient_negative,
    merge_relations,
    normalize_record_text,
    parse_record,
    render_context,
    render_current_speaker,
    render_group_roster,
    select_records,
)


STATE_VERSION = 4


@register(
    "group_persistent_memory",
    "keita",
    "Keeps isolated persistent chat memory for allowlisted QQ groups.",
    "1.3.0",
)
class GroupPersistentMemory(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._lock = asyncio.Lock()
        self._cache: dict[str, list[MemoryRecord]] = {}

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE, priority=100)
    async def record_group_message(self, event: AstrMessageEvent) -> None:
        if not self._is_allowed_group(event):
            return
        if str(event.get_sender_id() or "") == str(event.get_self_id() or ""):
            return
        text = normalize_record_text(
            event.get_message_str() or "",
            self._max_message_chars(),
        )
        if (
            not text
            or looks_sensitive(text)
            or (
                self._forget_negative_messages()
                and looks_transient_negative(text)
            )
        ):
            return
        records = await self._load(event)
        relations = self._event_relations(event, text, records)
        await self._append(
            event,
            MemoryRecord(
                timestamp=time.time(),
                role="user",
                sender_id=str(event.get_sender_id() or ""),
                sender_name=self._sender_name(event),
                text=text,
                relations=relations,
            ),
        )

    @filter.on_llm_request()
    async def inject_group_memory(
        self,
        event: AstrMessageEvent,
        request: ProviderRequest,
    ) -> None:
        if not self._is_allowed_group(event):
            return
        if event.get_extra("_mention_only_llm_allow") == "tarot_reading":
            return
        current_sender_id = str(event.get_sender_id() or "")
        current_sender_name = self._sender_name(event)
        request.extra_user_content_parts.append(
            TextPart(
                text=render_current_speaker(
                    current_sender_id,
                    current_sender_name,
                )
            )
        )
        query_parts = [str(request.prompt or "")]
        current_text = ""
        with suppress(Exception):
            current_text = normalize_record_text(event.get_message_str() or "", 1000)
            query_parts.append(current_text)
        records = await self._load(event)
        roster_text = render_group_roster(
            records,
            current_sender_id=current_sender_id,
            current_sender_name=current_sender_name,
            max_members=self._bounded("max_roster_members", 30, 5, 100),
        )
        if roster_text:
            request.extra_user_content_parts.append(
                TextPart(text=roster_text).mark_as_temp()
            )
        if (
            current_text
            and records
            and records[-1].role == "user"
            and records[-1].sender_id == current_sender_id
            and records[-1].text == current_text
        ):
            records = records[:-1]
        selected = select_records(
            records,
            "\n".join(query_parts),
            current_sender_id=current_sender_id,
            max_relevant=self._bounded("max_relevant_records", 6, 0, 20),
            recent_count=self._bounded("recent_records", 4, 0, 12),
            personal_count=self._bounded("personal_records", 2, 0, 8),
            max_chars=self._bounded("max_injected_chars", 5000, 500, 12000),
        )
        context_text = render_context(selected)
        if context_text:
            request.extra_user_content_parts.append(
                TextPart(text=context_text).mark_as_temp()
            )

    @filter.on_llm_response()
    async def record_bot_response(
        self,
        event: AstrMessageEvent,
        response: LLMResponse,
    ) -> None:
        if not self._is_allowed_group(event):
            return
        if event.get_extra("_mention_only_llm_allow") == "tarot_reading":
            return
        text = normalize_record_text(
            getattr(response, "completion_text", "") or "",
            self._max_message_chars(),
        )
        if (
            not text
            or looks_sensitive(text)
            or (
                self._forget_negative_messages()
                and looks_transient_negative(text)
            )
        ):
            return
        await self._append(
            event,
            MemoryRecord(
                timestamp=time.time(),
                role="assistant",
                sender_id=str(event.get_self_id() or ""),
                sender_name="机器人",
                text=text,
                reply_to_sender_id=str(event.get_sender_id() or ""),
                reply_to_sender_name=self._sender_name(event),
            ),
        )

    @filter.command("groupmemory", alias={"群记忆"})
    async def groupmemory(self, event: AstrMessageEvent, action: str = "status"):
        """Inspect or clear the isolated memory for the current group."""
        if not self._is_allowed_group(event):
            yield event.plain_result("群记忆仅对白名单群聊生效。")
            return
        normalized_action = str(action or "status").casefold().strip()
        if normalized_action in {"status", "状态"}:
            records = await self._load(event)
            user_count = sum(record.role == "user" for record in records)
            bot_count = len(records) - user_count
            yield event.plain_result(
                f"当前群记忆：{len(records)} 条\n"
                f"群成员消息：{user_count} 条\n机器人回复：{bot_count} 条\n"
                "各白名单群的记忆彼此隔离。"
            )
            return
        if normalized_action in {"clear", "清空"}:
            if not self._can_manage(event):
                yield event.plain_result("仅机器人作者、机器人管理员、群主或群管理员可清空群记忆。")
                return
            async with self._lock:
                key = self._group_key(event)
                self._cache[key] = []
                await self.put_kv_data(self._state_key(key), self._serialize([]))
            yield event.plain_result("当前群的持久化记忆已清空，其他群不受影响。")
            return
        yield event.plain_result("用法：/groupmemory status 或 /groupmemory clear")

    async def _append(self, event: AstrMessageEvent, record: MemoryRecord) -> None:
        async with self._lock:
            key = self._group_key(event)
            records = await self._load_locked(key)
            records = append_record(
                records,
                record,
                max_records=self._bounded("max_records_per_group", 500, 20, 3000),
                max_age_days=self._bounded("max_age_days", 180, 1, 3650),
            )
            self._cache[key] = records
            await self.put_kv_data(self._state_key(key), self._serialize(records))

    async def _load(self, event: AstrMessageEvent) -> list[MemoryRecord]:
        async with self._lock:
            return list(await self._load_locked(self._group_key(event)))

    async def _load_locked(self, key: str) -> list[MemoryRecord]:
        if key in self._cache:
            return self._cache[key]
        raw = await self.get_kv_data(self._state_key(key), {"records": []})
        raw_records = raw.get("records", []) if isinstance(raw, dict) else []
        parsed = [record for item in raw_records if (record := parse_record(item))]
        records = filter_durable_records(
            parsed,
            forget_negative=self._forget_negative_messages(),
        )
        if len(records) != len(parsed):
            logger.info(
                "Pruned %s transient negative group-memory records.",
                len(parsed) - len(records),
            )
            await self.put_kv_data(self._state_key(key), self._serialize(records))
        self._cache[key] = records
        return records

    @staticmethod
    def _serialize(records: list[MemoryRecord]) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "records": [record.to_dict() for record in records],
        }

    def _is_allowed_group(self, event: AstrMessageEvent) -> bool:
        if event.get_platform_name() not in {"qq_official", "aiocqhttp"}:
            return False
        try:
            root_config = self.context.get_config(event.unified_msg_origin)
            platform_settings = root_config.get("platform_settings", {})
        except Exception as exc:
            logger.warning("Unable to read AstrBot allowlist for group memory: %s", exc)
            return False
        return is_allowlisted_group(
            is_group=bool(event.get_group_id()),
            whitelist_enabled=bool(platform_settings.get("enable_id_white_list", False)),
            whitelist=platform_settings.get("id_whitelist", []),
            group_id=event.get_group_id(),
            unified_msg_origin=event.unified_msg_origin,
        )

    @staticmethod
    def _group_key(event: AstrMessageEvent) -> str:
        identity = "|".join(
            (
                str(event.get_platform_id() or event.get_platform_name() or "qq"),
                str(event.get_group_id() or ""),
            )
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _state_key(group_key: str) -> str:
        return f"group_memory_v1_{group_key}"

    @staticmethod
    def _sender_name(event: AstrMessageEvent) -> str:
        getter = getattr(event, "get_sender_name", None)
        if callable(getter):
            with suppress(Exception):
                name = str(getter() or "").strip()
                if name:
                    return name[:50]
        return "群成员"

    def _max_message_chars(self) -> int:
        return self._bounded("max_message_chars", 600, 80, 2000)

    def _forget_negative_messages(self) -> bool:
        return bool(self.config.get("forget_negative_messages", True))

    @classmethod
    def _event_relations(
        cls,
        event: AstrMessageEvent,
        text: str,
        records: list[MemoryRecord],
    ) -> tuple[MemberRelation, ...]:
        self_id = str(event.get_self_id() or "")
        relations: list[MemberRelation] = []
        for component in event.get_messages():
            if isinstance(component, Reply):
                relation = cls._relation_from_values(
                    "reply",
                    getattr(component, "sender_id", ""),
                    getattr(component, "sender_nickname", ""),
                    self_id=self_id,
                )
                if relation:
                    relations.append(relation)
            elif isinstance(component, At):
                relation = cls._relation_from_values(
                    "at",
                    getattr(component, "qq", ""),
                    getattr(component, "name", ""),
                    self_id=self_id,
                )
                if relation:
                    relations.append(relation)

        raw_message = getattr(event.message_obj, "raw_message", None)
        raw_data = getattr(raw_message, "raw_data", raw_message)
        mention_sets = [getattr(raw_message, "mentions", None)]
        if isinstance(raw_data, dict):
            mention_sets.append(raw_data.get("mentions"))
        for mention_set in mention_sets:
            if not isinstance(mention_set, (list, tuple)):
                continue
            for mention in mention_set:
                if bool(cls._field(mention, "is_you")):
                    continue
                relation = cls._relation_from_container(
                    "at",
                    mention,
                    self_id=self_id,
                )
                if relation:
                    relations.append(relation)

        relations.extend(
            find_nickname_relations(
                text,
                records,
                current_sender_id=str(event.get_sender_id() or ""),
            )
        )
        return merge_relations(relations)

    @classmethod
    def _relation_from_container(
        cls,
        kind: str,
        container: object,
        *,
        self_id: str,
    ) -> MemberRelation | None:
        member_id = ""
        for field in ("member_openid", "user_openid", "user_id", "id", "qq"):
            value = cls._field(container, field)
            if value not in (None, ""):
                member_id = str(value).strip()
                break
        member_name = ""
        for field in ("username", "nickname", "name"):
            value = cls._field(container, field)
            if value not in (None, ""):
                member_name = str(value).strip()
                break
        return cls._relation_from_values(
            kind,
            member_id,
            member_name,
            self_id=self_id,
        )

    @staticmethod
    def _relation_from_values(
        kind: str,
        member_id: object,
        member_name: object,
        *,
        self_id: str,
    ) -> MemberRelation | None:
        normalized_id = str(member_id or "").strip()
        normalized_name = normalize_record_text(member_name, 50)
        if normalized_id in {"all", "qq_official", self_id}:
            return None
        if normalized_id == "0":
            normalized_id = ""
        if not (normalized_id or normalized_name):
            return None
        return MemberRelation(kind, normalized_id, normalized_name)

    @staticmethod
    def _field(container: object, name: str) -> object:
        if isinstance(container, dict):
            return container.get(name)
        return getattr(container, name, None)

    def _bounded(self, name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(self.config.get(name, default))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    def _can_manage(self, event: AstrMessageEvent) -> bool:
        sender_id = str(event.get_sender_id() or "").strip()
        manager_ids = {
            str(value).strip()
            for value in self.config.get("manager_ids", [])
            if str(value).strip()
        }
        if sender_id in manager_ids or event.is_admin():
            return True
        raw_message = getattr(event.message_obj, "raw_message", None)
        raw = getattr(raw_message, "raw_data", raw_message)
        values: list[Any] = []
        if isinstance(raw, dict):
            for container_name in ("author", "member", "sender"):
                container = raw.get(container_name)
                if isinstance(container, dict):
                    values.extend((container.get("role"), container.get("roles")))
            values.extend((raw.get("role"), raw.get("roles")))
        roles: set[str] = set()
        for value in values:
            if isinstance(value, list):
                roles.update(str(item).casefold().strip() for item in value)
            elif value is not None:
                roles.add(str(value).casefold().strip())
        return bool(roles.intersection({"owner", "admin", "administrator", "群主", "管理员"}))
