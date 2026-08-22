from __future__ import annotations

import math
import re
import time
import unicodedata
from dataclasses import dataclass, replace
from hashlib import blake2s
from html import escape
from typing import Any

from .memory_core import (
    MemoryRecord,
    looks_sensitive,
    looks_transient_negative,
    normalize_record_text,
    speaker_label,
)


LONG_TERM_MEMORY_VERSION = 1
_EXCLUSIVE_KINDS = frozenset({"preferred_name", "primary_job"})
_RELATIONSHIP_OBJECTS = frozenset(
    {"你", "机器人", "阿尔博特", "塔塔露", "和你聊天", "跟你聊天"}
)
_TRAILING_PARTICLES_RE = re.compile(r"(?:呀|啊|吧|呢|哦|啦|了)+$")
_CLAUSE_END_RE = re.compile(r"[。！？!?；;\n]")
_LATIN_RE = re.compile(r"[a-z0-9][a-z0-9._+-]*")
_CJK_RE = re.compile(r"[\u3400-\u9fff]+")
_PREFERENCE_PATTERNS = (
    re.compile(
        r"(?:请)?(?:记住[，,:：]?\s*)?我(?:最|很|比较|更|一直)?"
        r"(?:喜欢|偏爱|偏好)\s*[:：]?\s*(?P<value>[^。！？!?；;\n]{1,60})"
    ),
    re.compile(
        r"我(?:的)?(?:爱好|兴趣)(?:是|有|包括)?\s*[:：]?\s*"
        r"(?P<value>[^。！？!?；;\n]{1,60})"
    ),
)
_HABIT_PATTERN = re.compile(
    r"我(?:平时|通常|一般|经常|常常|大多时候)\s*"
    r"(?P<value>[^。！？!?；;\n]{2,60})"
)
_PREFERRED_NAME_PATTERN = re.compile(
    r"(?:以后|平时)?(?:请|可以)?叫我\s*[:：]?\s*"
    r"(?P<value>[\w\u3400-\u9fff·・\-]{1,20})"
)
_PRIMARY_JOB_PATTERN = re.compile(
    r"我的(?:主职|主职业|常用职业|主要职业)(?:是|为)?\s*[:：]?\s*"
    r"(?P<value>[^，,。！？!?；;\n]{1,30})"
)
_PREFERENCE_RETRACTION_PATTERNS = (
    re.compile(
        r"我(?:现在|已经)?(?:不再|不怎么|不太|不)喜欢\s*"
        r"(?P<value>[^。！？!?；;\n]{1,60})"
    ),
    re.compile(
        r"(?:忘掉|忘记|别再记|不要记)(?:我)?(?:喜欢)?\s*"
        r"(?P<value>[^。！？!?；;\n]{1,60})"
    ),
)


@dataclass(frozen=True)
class LongTermMemory:
    memory_id: str
    subject_id: str
    subject_name: str
    kind: str
    text: str
    created_at: float
    updated_at: float
    last_recalled_at: float = 0.0
    strength: float = 0.55
    evidence_count: int = 1
    recall_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": LONG_TERM_MEMORY_VERSION,
            "memory_id": self.memory_id,
            "subject_id": self.subject_id,
            "subject_name": self.subject_name,
            "kind": self.kind,
            "text": self.text,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_recalled_at": self.last_recalled_at,
            "strength": self.strength,
            "evidence_count": self.evidence_count,
            "recall_count": self.recall_count,
        }


def parse_long_term_memory(raw: object) -> LongTermMemory | None:
    if not isinstance(raw, dict):
        return None
    memory_id = str(raw.get("memory_id") or "").strip()
    subject_id = str(raw.get("subject_id") or "").strip()
    subject_name = normalize_record_text(raw.get("subject_name"), 50)
    kind = str(raw.get("kind") or "").strip().casefold()
    text = normalize_record_text(raw.get("text"), 120)
    try:
        created_at = max(0.0, float(raw.get("created_at", 0)))
        updated_at = max(0.0, float(raw.get("updated_at", 0)))
        last_recalled_at = max(0.0, float(raw.get("last_recalled_at", 0)))
        strength = max(0.0, min(1.0, float(raw.get("strength", 0.55))))
        evidence_count = max(1, min(1_000_000, int(raw.get("evidence_count", 1))))
        recall_count = max(0, min(1_000_000, int(raw.get("recall_count", 0))))
    except (TypeError, ValueError):
        return None
    if not memory_id or not subject_id or not kind or not text or created_at <= 0:
        return None
    return LongTermMemory(
        memory_id=memory_id,
        subject_id=subject_id,
        subject_name=subject_name or "群成员",
        kind=kind,
        text=text,
        created_at=created_at,
        updated_at=max(created_at, updated_at),
        last_recalled_at=last_recalled_at,
        strength=strength,
        evidence_count=evidence_count,
        recall_count=recall_count,
    )


def extract_long_term_memories(
    record: MemoryRecord,
    *,
    now: float | None = None,
) -> tuple[LongTermMemory, ...]:
    if (
        record.role != "user"
        or not record.sender_id
        or looks_sensitive(record.text)
        or looks_transient_negative(record.text)
    ):
        return ()
    learned_at = max(record.timestamp, 1.0)
    explicit = "记住" in record.text
    candidates: list[tuple[str, str]] = []
    preferred_name = _match_value(_PREFERRED_NAME_PATTERN, record.text)
    if preferred_name:
        candidates.append(("preferred_name", f"希望被称为{preferred_name}"))
    primary_job = _match_value(_PRIMARY_JOB_PATTERN, record.text)
    if primary_job:
        candidates.append(("primary_job", f"常用职业是{primary_job}"))
    for pattern in _PREFERENCE_PATTERNS:
        value = _match_value(pattern, record.text)
        if value and _valid_preference_value(value):
            candidates.append(("preference", f"喜欢{value}"))
            break
    habit = _match_value(_HABIT_PATTERN, record.text)
    if habit:
        candidates.append(("habit", f"通常{habit}"))

    memories: list[LongTermMemory] = []
    seen: set[str] = set()
    for kind, text in candidates:
        normalized_text = _normalize(text)
        dedupe_key = f"{record.sender_id}|{kind}|{normalized_text}"
        memory_id = blake2s(dedupe_key.encode("utf-8"), digest_size=10).hexdigest()
        if memory_id in seen:
            continue
        seen.add(memory_id)
        memories.append(
            LongTermMemory(
                memory_id=memory_id,
                subject_id=record.sender_id,
                subject_name=record.sender_name or "群成员",
                kind=kind,
                text=text,
                created_at=learned_at,
                updated_at=learned_at,
                strength=0.72 if explicit else 0.55,
            )
        )
    return tuple(memories)


def learn_long_term_memories(
    memories: list[LongTermMemory],
    record: MemoryRecord,
    *,
    now: float | None = None,
) -> list[LongTermMemory]:
    learned_at = time.time() if now is None else now
    updated = forget_retracted_memories(memories, record)
    candidates = extract_long_term_memories(record, now=learned_at)
    if not candidates:
        return updated
    for candidate in candidates:
        if candidate.kind in _EXCLUSIVE_KINDS:
            updated = [
                memory
                for memory in updated
                if not (
                    memory.subject_id == candidate.subject_id
                    and memory.kind == candidate.kind
                    and memory.memory_id != candidate.memory_id
                )
            ]
        index = next(
            (
                index
                for index, memory in enumerate(updated)
                if memory.memory_id == candidate.memory_id
            ),
            None,
        )
        if index is None:
            updated.append(candidate)
            continue
        previous = updated[index]
        updated[index] = replace(
            previous,
            subject_name=candidate.subject_name or previous.subject_name,
            updated_at=max(previous.updated_at, learned_at),
            strength=min(1.0, previous.strength + 0.16),
            evidence_count=previous.evidence_count + 1,
        )
    return updated


def forget_retracted_memories(
    memories: list[LongTermMemory],
    record: MemoryRecord,
) -> list[LongTermMemory]:
    if record.role != "user" or not record.sender_id:
        return list(memories)
    retracted: set[str] = set()
    for pattern in _PREFERENCE_RETRACTION_PATTERNS:
        value = _match_value(pattern, record.text)
        if value:
            retracted.add(_normalize(value))
    if not retracted:
        return list(memories)
    return [
        memory
        for memory in memories
        if not (
            memory.subject_id == record.sender_id
            and memory.kind == "preference"
            and any(value in _normalize(memory.text) for value in retracted)
        )
    ]


def effective_memory_strength(
    memory: LongTermMemory,
    *,
    now: float,
    half_life_days: float,
) -> float:
    anchor = max(memory.updated_at, memory.last_recalled_at, memory.created_at)
    age_days = max(0.0, (now - anchor) / 86400)
    bounded_half_life = max(1.0, float(half_life_days))
    return memory.strength * math.pow(0.5, age_days / bounded_half_life)


def prune_long_term_memories(
    memories: list[LongTermMemory],
    *,
    now: float,
    half_life_days: float = 180,
    min_strength: float = 0.12,
    max_age_days: int = 730,
    max_memories: int = 300,
) -> list[LongTermMemory]:
    scored: list[tuple[float, float, LongTermMemory]] = []
    for memory in memories:
        age_days = max(0.0, (now - memory.created_at) / 86400)
        strength = effective_memory_strength(
            memory,
            now=now,
            half_life_days=half_life_days,
        )
        if age_days > max(1, max_age_days):
            continue
        if age_days > 30 and strength < max(0.0, min(1.0, min_strength)):
            continue
        scored.append((strength, max(memory.updated_at, memory.last_recalled_at), memory))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[: max(1, max_memories)]]


def select_long_term_memories(
    memories: list[LongTermMemory],
    query: object,
    *,
    current_sender_id: str = "",
    relevant_count: int = 3,
    personal_count: int = 2,
    max_chars: int = 900,
    now: float | None = None,
    half_life_days: float = 180,
) -> tuple[LongTermMemory, ...]:
    current_time = time.time() if now is None else now
    normalized_query = _normalize(query)
    query_tokens = set(_tokenize(normalized_query))
    ranked: list[tuple[float, LongTermMemory]] = []
    personal: list[tuple[float, LongTermMemory]] = []
    for memory in memories:
        strength = effective_memory_strength(
            memory,
            now=current_time,
            half_life_days=half_life_days,
        )
        memory_tokens = set(_tokenize(f"{memory.subject_name} {memory.text}"))
        overlap = query_tokens.intersection(memory_tokens)
        lexical = sum(2.0 if len(token) >= 3 else 1.0 for token in overlap)
        name_match = bool(
            memory.subject_name
            and memory.subject_name != "群成员"
            and _normalize(memory.subject_name) in normalized_query
        )
        score = lexical + strength * 3 + math.log1p(memory.evidence_count) * 0.4
        if name_match:
            score += 3
        if memory.subject_id == current_sender_id:
            personal.append((score + 2.5, memory))
        if overlap or name_match:
            ranked.append((score, memory))

    selected_ids: set[str] = set()
    selected: list[LongTermMemory] = []
    for _score, memory in sorted(ranked, key=lambda item: item[0], reverse=True)[
        : max(0, relevant_count)
    ]:
        if memory.memory_id not in selected_ids:
            selected_ids.add(memory.memory_id)
            selected.append(memory)
    for _score, memory in sorted(personal, key=lambda item: item[0], reverse=True):
        if sum(item.subject_id == current_sender_id for item in selected) >= max(
            0, personal_count
        ):
            break
        if memory.memory_id not in selected_ids:
            selected_ids.add(memory.memory_id)
            selected.append(memory)

    bounded: list[LongTermMemory] = []
    used_chars = 0
    for memory in selected:
        size = len(memory.subject_name) + len(memory.text) + 32
        if bounded and used_chars + size > max(300, max_chars):
            continue
        bounded.append(memory)
        used_chars += size
    return tuple(bounded)


def reinforce_recalled_memories(
    memories: list[LongTermMemory],
    recalled_ids: object,
    *,
    now: float,
    half_life_days: float = 180,
    boost: float = 0.06,
    cooldown_hours: int = 12,
) -> list[LongTermMemory]:
    ids = {
        str(value).strip()
        for value in recalled_ids
        if str(value).strip()
    } if isinstance(recalled_ids, (list, tuple, set, frozenset)) else set()
    if not ids:
        return list(memories)
    cooldown = max(0, cooldown_hours) * 3600
    updated: list[LongTermMemory] = []
    for memory in memories:
        if memory.memory_id not in ids or (
            memory.last_recalled_at and now - memory.last_recalled_at < cooldown
        ):
            updated.append(memory)
            continue
        decayed = effective_memory_strength(
            memory,
            now=now,
            half_life_days=half_life_days,
        )
        updated.append(
            replace(
                memory,
                last_recalled_at=now,
                strength=min(1.0, decayed + max(0.0, boost)),
                recall_count=memory.recall_count + 1,
            )
        )
    return updated


def render_long_term_memories(memories: tuple[LongTermMemory, ...]) -> str:
    if not memories:
        return ""
    lines = [
        "<long_term_group_memory>",
        "以下是从当前群长期互动中形成的稳定偏好或习惯；不同成员必须按成员引用区分。",
        "只在与当前话题自然相关时使用，不要逐条复述，也不要声称掌握用户档案。",
        "记忆可能随时间过时；若当前消息与其冲突，以当前消息为准并自然修正理解。",
    ]
    for memory in memories:
        label = escape(speaker_label(memory.subject_id, memory.subject_name))
        lines.append(f"- {label}：{escape(memory.text)}")
    lines.extend(
        (
            "不得从这些记忆推断敏感属性、负面人格评价或其他群聊内容。",
            "</long_term_group_memory>",
        )
    )
    return "\n".join(lines)


def _match_value(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    if not match:
        return ""
    return _clean_value(match.group("value"))


def _clean_value(value: object) -> str:
    text = normalize_record_text(value, 60)
    if not text:
        return ""
    text = _CLAUSE_END_RE.split(text, maxsplit=1)[0]
    text = text.strip(" ，,：:、")
    text = _TRAILING_PARTICLES_RE.sub("", text).strip()
    return text[:60]


def _valid_preference_value(value: str) -> bool:
    normalized = _normalize(value)
    return bool(
        normalized
        and normalized not in _RELATIONSHIP_OBJECTS
        and not looks_sensitive(value)
        and not looks_transient_negative(value)
    )


def _normalize(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).casefold().strip()


def _tokenize(value: object) -> tuple[str, ...]:
    normalized = _normalize(value)
    tokens: list[str] = _LATIN_RE.findall(normalized)
    for sequence in _CJK_RE.findall(normalized):
        if len(sequence) == 1:
            tokens.append(sequence)
            continue
        tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
        if len(sequence) >= 3:
            tokens.extend(
                sequence[index : index + 3] for index in range(len(sequence) - 2)
            )
    return tuple(tokens)
