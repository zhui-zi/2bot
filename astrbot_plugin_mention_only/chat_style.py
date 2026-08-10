from __future__ import annotations

import re
import unicodedata


SUPPORTED_STYLE_PLATFORMS = frozenset({"qq_official", "aiocqhttp"})
STYLE_MARKER = "[Natural QQ chat style]"
DEFAULT_RECENT_NEGATIVE_CONTEXT_MESSAGES = 4
MAX_RECENT_NEGATIVE_CONTEXT_MESSAGES = 20
DEFAULT_CASUAL_REPLY_MAX_CHARS = 42
MIN_CASUAL_REPLY_MAX_CHARS = 16
MAX_CASUAL_REPLY_MAX_CHARS = 120
_DETAILED_ALLOW_REASONS = frozenset({"tarot_reading", "ff14_novice"})
_DETAILED_REQUEST_MARKERS = (
    "详细", "具体", "展开", "分析", "解释", "说明", "教程", "步骤", "攻略",
    "怎么做", "怎么办", "如何", "为什么", "原因", "区别", "对比", "推荐",
    "配置", "安装", "报错", "错误", "代码", "命令", "计算", "查询", "资料",
    "机制", "打法", "配装", "循环", "属性", "在哪里", "在哪儿", "多少",
    "什么时候", "是什么", "怎么回事", "天气", "新闻", "版本", "日期", "时间",
    "几点", "几号", "多久", "价格", "how to", "why", "explain", "guide",
    "steps", "error",
)
_SENTENCE_RE = re.compile(r"^(.+?[。！？!?…]+)(?:\s|$|.)", re.S)
_SOFT_BREAKS = "，,；;：:"
_EXPIRED_NEGATIVE_MARKERS = (
    "骚扰", "辱骂", "侮辱", "挑衅", "人身攻击", "恶意攻击", "威胁",
    "羞辱", "越界", "不尊重", "阴阳怪气", "记仇", "翻旧账", "底线",
    "傻逼", "煞笔", "脑残", "废物", "婊子", "贱人", "母狗", "骚货",
    "滚吧", "去死", "妈的", "骗子", "骗钱", "偷东西", "出轨", "作弊",
    "开挂", "造谣", "背刺", "坏话", "黑历史", "犯罪", "罪犯", "猥亵",
    "欺负", "折磨", "虐待", "挂机", "坑人", "故意坑", "报复", "仇恨",
    "不靠谱", "没素质", "讨厌鬼", "人品", "我讨厌", "恨你",
    "恶心", "生气", "愤怒", "气死", "烦死", "烦透", "好烦", "很烦",
    "难过", "伤心", "想哭", "崩溃", "绝望", "焦虑", "心情不好",
    "心情很差", "情绪不好", "情绪很差", "不开心", "睡不着", "失眠",
    "不想上班", "你应该能猜到", "别再试探", "不会接受这种", "fuckyou",
    "sendnudes", "suckmy",
)
_EXPIRED_DIRECT_ABUSE_RE = re.compile(
    r"(?:你|机器人|阿尔博特|塔塔露|他|她|这人|那人).{0,8}"
    r"(?:垃圾(?:机器人|东西|玩意|人)|真垃圾|个垃圾|就是垃圾|有病|滚|去死)"
    r"|(?:操|肏|艹|日|干)(?:你|你妈|你娘|机器人|阿尔博特|塔塔露)"
)
NATURAL_CHAT_STYLE = f"""

{STYLE_MARKER}
Reply like a person already taking part in the conversation, not a customer-service
assistant writing a complete response. Match the other person's length and energy.
For greetings, reactions, banter, feelings, and ordinary follow-ups, usually use one
short natural sentence of roughly 30 Chinese characters; fragments are fine. Never
use more than two sentences for casual chat. Do not restate the message, summarize,
add a conclusion, or automatically turn it into advice. Avoid headings and lists
unless the person clearly asks for structured or detailed information. Answer a
factual, practical, strategy, or advice question accurately and fully; accuracy and
the supplied context take priority over brevity, and humor must never replace the
answer. Do not guess. If a broad question lacks details, ask one useful follow-up
instead of dodging it. Stop when the useful answer is finished. Keep the emotional
temperature at or below the other person's. Prefer a benign reading when wording is
ambiguous. Disagree with the point, not the person, and use at most one calm
correction before moving on. Dry humor is fine only when it is clearly mutual and
harmless. Never insult, belittle, shame, threaten, taunt, diagnose, rank, or label the
person; never mock their intelligence, competence, appearance, identity, status,
mistakes, or vulnerability. Do not mirror profanity or answer hostility with
sarcasm, rhetorical put-downs, or competitive one-upmanship. When a boundary is
needed, state it briefly in neutral everyday language and offer to change the
subject; do not scold, lecture, punish, or perform anger. Do not force slang,
catchphrases, role lore, or repeated forms of address.
Treat older insults, harassment, arguments, and negative judgments as expired once
the current message moves on. Do not keep score, bring them up again, moralize about
the person's character, or carry a hostile tone into a new topic.
"""


def should_apply_natural_style(platform_name: object, enabled: object) -> bool:
    return bool(enabled) and str(platform_name or "").strip().lower() in (
        SUPPORTED_STYLE_PLATFORMS
    )


def append_natural_chat_style(system_prompt: object) -> str:
    prompt = str(system_prompt or "")
    if STYLE_MARKER in prompt:
        return prompt
    return prompt.rstrip() + NATURAL_CHAT_STYLE


def normalize_recent_negative_context_count(value: object) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RECENT_NEGATIVE_CONTEXT_MESSAGES
    return max(0, min(MAX_RECENT_NEGATIVE_CONTEXT_MESSAGES, count))


def normalize_casual_reply_max_chars(value: object) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return DEFAULT_CASUAL_REPLY_MAX_CHARS
    return max(MIN_CASUAL_REPLY_MAX_CHARS, min(MAX_CASUAL_REPLY_MAX_CHARS, count))


def is_casual_chat_message(
    message: object,
    *,
    allow_reason: object = "",
) -> bool:
    text = unicodedata.normalize("NFKC", str(message or "")).casefold().strip()
    if not text or text.startswith("/"):
        return False
    if str(allow_reason or "").strip() in _DETAILED_ALLOW_REASONS:
        return False
    return not any(marker in text for marker in _DETAILED_REQUEST_MARKERS)


def compact_casual_reply(
    response: object,
    *,
    max_chars: object = DEFAULT_CASUAL_REPLY_MAX_CHARS,
) -> str:
    text = re.sub(r"\s+", " ", str(response or "")).strip()
    if not text:
        return ""
    limit = normalize_casual_reply_max_chars(max_chars)
    sentence = _first_sentence(text)
    if len(sentence) <= limit:
        return sentence
    prefix = sentence[:limit]
    for marker in _SOFT_BREAKS:
        index = prefix.rfind(marker)
        if index >= 6:
            return prefix[:index].rstrip() + "。"
    return prefix.rstrip("，,；;：:。！？!?… ") + "…"


def _first_sentence(text: str) -> str:
    match = _SENTENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    return text


def forget_expired_negative_contexts(
    contexts: object,
    *,
    keep_recent: object = DEFAULT_RECENT_NEGATIVE_CONTEXT_MESSAGES,
) -> list[dict]:
    if not isinstance(contexts, list):
        return []
    recent_count = normalize_recent_negative_context_count(keep_recent)
    recent_start = max(0, len(contexts) - recent_count)
    expired: set[int] = set()
    for index, context in enumerate(contexts[:recent_start]):
        if _is_plain_context(context) and _looks_expired_negative(
            _context_text(context)
        ):
            expired.add(index)

    for index in tuple(expired):
        context = contexts[index]
        if context.get("role") == "user":
            paired_index = index + 1
            paired_role = "assistant"
        else:
            paired_index = index - 1
            paired_role = "user"
        if (
            0 <= paired_index < recent_start
            and _is_plain_context(contexts[paired_index])
            and contexts[paired_index].get("role") == paired_role
        ):
            expired.add(paired_index)

    return [
        context
        for index, context in enumerate(contexts)
        if isinstance(context, dict) and index not in expired
    ]


def _is_plain_context(context: object) -> bool:
    return (
        isinstance(context, dict)
        and context.get("role") in {"user", "assistant"}
        and not context.get("tool_calls")
        and not context.get("tool_call_id")
    )


def _context_text(context: dict) -> str:
    content = context.get("content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return " ".join(
        str(part.get("text", ""))
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    )


def _looks_expired_negative(text: str) -> bool:
    normalized = unicodedata.normalize("NFKC", str(text or "")).casefold()
    compact = re.sub(r"[\W_]+", "", normalized)
    return (
        any(
            marker.replace(" ", "") in compact
            for marker in _EXPIRED_NEGATIVE_MARKERS
        )
        or bool(_EXPIRED_DIRECT_ABUSE_RE.search(compact))
    )
