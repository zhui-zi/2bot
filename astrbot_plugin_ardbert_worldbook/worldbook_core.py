from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_PLATFORMS = frozenset({"qq_official", "aiocqhttp"})


@dataclass(frozen=True)
class WorldbookEntry:
    entry_id: str
    title: str
    keywords: tuple[str, ...]
    content: str
    spoiler: str = "safe"
    priority: int = 0


@dataclass(frozen=True)
class Worldbook:
    entries: tuple[WorldbookEntry, ...]
    max_entries: int = 3
    max_chars: int = 2400


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def is_supported_platform(platform_name: str) -> bool:
    return normalize_text(str(platform_name).strip()) in SUPPORTED_PLATFORMS


def load_worldbook(path: Path) -> Worldbook:
    payload = json.loads(path.read_text(encoding="utf-8"))
    settings = payload.get("settings", {})
    entries = tuple(_parse_entry(raw) for raw in payload.get("entries", []))
    if not entries:
        raise ValueError("worldbook must contain at least one entry")
    entry_ids = [entry.entry_id for entry in entries]
    if len(entry_ids) != len(set(entry_ids)):
        raise ValueError("worldbook entry ids must be unique")
    return Worldbook(
        entries=entries,
        max_entries=max(1, int(settings.get("max_entries", 3))),
        max_chars=max(256, int(settings.get("max_chars", 2400))),
    )


def _parse_entry(raw: dict[str, Any]) -> WorldbookEntry:
    entry_id = str(raw.get("id", "")).strip()
    title = str(raw.get("title", "")).strip()
    content = str(raw.get("content", "")).strip()
    keywords = tuple(
        str(keyword).strip()
        for keyword in raw.get("keywords", [])
        if str(keyword).strip()
    )
    if not entry_id or not title or not content or not keywords:
        raise ValueError("each worldbook entry needs id, title, keywords, and content")
    return WorldbookEntry(
        entry_id=entry_id,
        title=title,
        keywords=keywords,
        content=content,
        spoiler=str(raw.get("spoiler", "safe")).strip() or "safe",
        priority=int(raw.get("priority", 0)),
    )


def select_entries(worldbook: Worldbook, query: str) -> tuple[WorldbookEntry, ...]:
    normalized_query = normalize_text(query)
    ranked: list[tuple[int, int, str, WorldbookEntry]] = []
    for entry in worldbook.entries:
        matches = [
            normalize_text(keyword)
            for keyword in entry.keywords
            if normalize_text(keyword) in normalized_query
        ]
        if not matches:
            continue
        longest_match = max(len(match) for match in matches)
        score = entry.priority + longest_match * 10 + len(matches)
        ranked.append((-score, -longest_match, entry.entry_id, entry))

    selected: list[WorldbookEntry] = []
    used_chars = 0
    for _, _, _, entry in sorted(ranked):
        entry_size = len(entry.title) + len(entry.spoiler) + len(entry.content)
        if selected and used_chars + entry_size > worldbook.max_chars:
            continue
        selected.append(entry)
        used_chars += entry_size
        if len(selected) >= worldbook.max_entries:
            break
    return tuple(selected)


def render_context(entries: tuple[WorldbookEntry, ...]) -> str:
    if not entries:
        return ""
    sections = [
        "<ardbert_worldbook>",
        "以下是本轮话题相关的原创设定摘要。将其作为事实边界自然作答，不要逐条背诵，也不要声称正在读取世界书。",
        "safe 可直接使用；标有版本号的条目涉及剧情剧透。仅回答用户明确问到的范围，必要时先用一句话提示剧透，不主动扩展后续真相。",
        "玩家角色的姓名、性别、种族与经历由用户决定；统一称为‘那位冒险者’或‘原初世界的光之战士’，不得擅自设定。",
    ]
    for entry in entries:
        sections.append(
            f"\n[{entry.title} | spoiler={entry.spoiler}]\n{entry.content}"
        )
    sections.append("</ardbert_worldbook>")
    return "\n".join(sections)
