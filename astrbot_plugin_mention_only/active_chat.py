from __future__ import annotations


SUPPORTED_PLATFORMS = frozenset({"qq_official", "aiocqhttp"})
TRUSTED_LLM_ALLOW_REASONS = frozenset(
    {"tarot_reading", "active_reply", "ff14_novice"}
)
MAX_ACTIVE_REPLY_PERCENT = 30.0
DEFAULT_ACTIVE_REPLY_COOLDOWN_MINUTES = 30.0
MAX_ACTIVE_REPLY_COOLDOWN_MINUTES = 1440.0


def normalize_reply_percent(value: object) -> float:
    try:
        percent = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(MAX_ACTIVE_REPLY_PERCENT, percent))


def is_active_reply_candidate(
    *,
    platform_name: str,
    is_group_chat: bool,
    is_explicit_trigger: bool,
    sender_id: str,
    self_id: str,
    message: str,
) -> bool:
    text = message.strip()
    return (
        platform_name.strip().lower() in SUPPORTED_PLATFORMS
        and is_group_chat
        and not is_explicit_trigger
        and bool(text)
        and not text.startswith("/")
        and sender_id != self_id
    )


def should_reply(percent: object, random_sample: float) -> bool:
    return random_sample < normalize_reply_percent(percent) / 100.0


def normalize_reply_cooldown_minutes(value: object) -> float:
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        return DEFAULT_ACTIVE_REPLY_COOLDOWN_MINUTES
    return max(0.0, min(MAX_ACTIVE_REPLY_COOLDOWN_MINUTES, minutes))


def active_reply_cooldown_elapsed(
    last_reply_at: object,
    now: object,
    cooldown_minutes: object,
) -> bool:
    try:
        last = float(last_reply_at)
        current = float(now)
    except (TypeError, ValueError):
        return True
    cooldown_seconds = normalize_reply_cooldown_minutes(cooldown_minutes) * 60.0
    return current < last or current - last >= cooldown_seconds


def should_quote_group_reply(
    *,
    platform_name: object,
    is_group_chat: object,
    message_id: object,
) -> bool:
    return (
        str(platform_name or "").strip().casefold() == "aiocqhttp"
        and bool(is_group_chat)
        and bool(str(message_id or "").strip())
    )


def should_allow_llm_request(
    *,
    platform_name: str,
    is_private_chat: bool,
    targets_bot: bool,
    allow_reason: str,
) -> bool:
    if platform_name != "qq_official":
        return True
    if allow_reason in TRUSTED_LLM_ALLOW_REASONS:
        return True
    return not is_private_chat and targets_bot
