from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_PLATFORMS = frozenset({"qq_official", "aiocqhttp"})


@dataclass(frozen=True)
class MemeEntry:
    entry_id: str
    title: str
    keywords: tuple[str, ...]
    meaning: str
    reply_guidance: str
    tone: str = "banter"
    priority: int = 0


@dataclass(frozen=True)
class MemePack:
    entries: tuple[MemeEntry, ...]
    max_entries: int = 2
    max_chars: int = 1800


def normalize_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def is_supported_platform(platform_name: object) -> bool:
    return str(platform_name or "").strip().casefold() in SUPPORTED_PLATFORMS


def load_meme_pack(path: Path) -> MemePack:
    payload = json.loads(path.read_text(encoding="utf-8"))
    settings = payload.get("settings", {})
    entries = tuple(_parse_entry(raw) for raw in payload.get("entries", []))
    if not entries:
        raise ValueError("meme pack must contain at least one entry")
    entry_ids = [entry.entry_id for entry in entries]
    if len(entry_ids) != len(set(entry_ids)):
        raise ValueError("meme entry ids must be unique")
    return MemePack(
        entries=entries,
        max_entries=max(1, int(settings.get("max_entries", 2))),
        max_chars=max(256, int(settings.get("max_chars", 1800))),
    )


def _parse_entry(raw: dict[str, Any]) -> MemeEntry:
    entry_id = str(raw.get("id", "")).strip()
    title = str(raw.get("title", "")).strip()
    meaning = str(raw.get("meaning", "")).strip()
    reply_guidance = str(raw.get("reply_guidance", "")).strip()
    keywords = tuple(
        str(keyword).strip()
        for keyword in raw.get("keywords", [])
        if str(keyword).strip()
    )
    if not entry_id or not title or not meaning or not reply_guidance or not keywords:
        raise ValueError(
            "each meme entry needs id, title, keywords, meaning, and reply_guidance"
        )
    if any(not normalize_text(keyword) for keyword in keywords):
        raise ValueError("meme keywords must contain searchable characters")
    return MemeEntry(
        entry_id=entry_id,
        title=title,
        keywords=keywords,
        meaning=meaning,
        reply_guidance=reply_guidance,
        tone=str(raw.get("tone", "banter")).strip() or "banter",
        priority=int(raw.get("priority", 0)),
    )


def select_entries(pack: MemePack, query: object) -> tuple[MemeEntry, ...]:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return ()

    ranked: list[tuple[int, int, str, MemeEntry]] = []
    for entry in pack.entries:
        matches = {
            normalized_keyword
            for keyword in entry.keywords
            if (normalized_keyword := normalize_text(keyword)) in normalized_query
        }
        if not matches:
            continue
        longest_match = max(len(match) for match in matches)
        score = entry.priority + longest_match * 10 + len(matches)
        ranked.append((-score, -longest_match, entry.entry_id, entry))

    selected: list[MemeEntry] = []
    used_chars = 0
    for _, _, _, entry in sorted(ranked):
        entry_size = (
            len(entry.title)
            + len(entry.meaning)
            + len(entry.reply_guidance)
            + len(entry.tone)
        )
        if selected and used_chars + entry_size > pack.max_chars:
            continue
        selected.append(entry)
        used_chars += entry_size
        if len(selected) >= pack.max_entries:
            break
    return tuple(selected)


def render_context(entries: tuple[MemeEntry, ...]) -> str:
    if not entries:
        return ""
    sections = [
        "<three_kingdoms_meme_context>",
        "以下是本轮消息命中的2010版电视剧《三国》网络梗。只把它们当作接话线索，不要声称亲历剧情或正在读取梗库。",
        "对方明显玩梗时，可以顺着当前语气接半句、轻改一句或作短反应；默认不要解释出处，不要连续堆梗，也不要为了玩梗跳过事实回答。",
        "普通同词、严肃求助或悼念语境不得硬玩梗。tone=solemn 的条目只保持克制，不做戏谑改写。",
    ]
    for entry in entries:
        sections.append(
            f"\n[{entry.title} | tone={entry.tone}]\n"
            f"含义：{entry.meaning}\n"
            f"接话：{entry.reply_guidance}"
        )
    sections.append("</three_kingdoms_meme_context>")
    return "\n".join(sections)
