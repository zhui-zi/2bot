from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree
from zoneinfo import ZoneInfo


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
BATTLEFIELD_ANCHOR = datetime(2026, 4, 28, 23, 0, tzinfo=SHANGHAI_TZ)
BATTLEFIELD_ROTATION = (
    ("阵地", "周边遗迹群（阵地战）"),
    ("草原", "昂萨哈凯尔（竞争战）"),
    ("沃刻", "沃刻其特（演习战）"),
    ("尘封", "尘封秘岩（争夺战）"),
    ("碎冰", "荣誉野（碎冰战）"),
    ("草原", "昂萨哈凯尔（竞争战）"),
    ("沃刻", "沃刻其特（演习战）"),
    ("尘封", "尘封秘岩（争夺战）"),
)

SUBSCRIPTION_DEFAULTS = {
    "news": False,
    "pvp": False,
    "house": False,
    "news_initialized": False,
    "news_seen": [],
    "battlefield_last_date": "",
    "house_servers": [],
    "house_sizes": [0, 1, 2],
    "house_audiences": ["personal", "fc"],
    "house_server_cycles": {},
    "house_result_cycle": "",
}


@dataclass(frozen=True)
class FeedItem:
    item_id: str
    title: str
    link: str
    published: str
    summary: str


def normalize_scene(value: Any) -> str:
    return "friend" if str(value).strip().lower() == "friend" else "group"


def resolve_qq_scene(
    platform_name: str,
    is_private_chat: bool,
    is_group_chat: bool,
) -> str:
    if platform_name.strip().lower() not in {"qq_official", "aiocqhttp"}:
        return ""
    if is_group_chat:
        return "group"
    return "friend" if is_private_chat else ""


def normalize_subscription(
    subscription: dict[str, Any] | None,
    target_id: str,
    scene: str,
) -> dict[str, Any]:
    current = subscription if isinstance(subscription, dict) else {}
    normalized_scene = normalize_scene(scene)
    current["scene"] = normalized_scene
    if normalized_scene == "friend":
        current["user_id"] = target_id
        current.pop("group_id", None)
    else:
        current["group_id"] = target_id
        current.pop("user_id", None)
    for key, value in SUBSCRIPTION_DEFAULTS.items():
        current.setdefault(
            key,
            value.copy() if isinstance(value, (list, dict)) else value,
        )
    if not isinstance(current.get("news_seen"), list):
        current["news_seen"] = []
    if not isinstance(current.get("house_servers"), list):
        current["house_servers"] = []
    if not isinstance(current.get("house_sizes"), list):
        current["house_sizes"] = [0, 1, 2]
    if not isinstance(current.get("house_audiences"), list):
        current["house_audiences"] = ["personal", "fc"]
    if not isinstance(current.get("house_server_cycles"), dict):
        current["house_server_cycles"] = {}
    if not isinstance(current.get("house_result_cycle"), str):
        current["house_result_cycle"] = ""
    return current


def battlefield_for_time(now: datetime) -> tuple[str, str]:
    local_now = now.astimezone(SHANGHAI_TZ)
    rotation_day = (local_now - BATTLEFIELD_ANCHOR).days
    return BATTLEFIELD_ROTATION[rotation_day % len(BATTLEFIELD_ROTATION)]


def battlefield_rotation_text(now: datetime) -> str:
    local_now = now.astimezone(SHANGHAI_TZ)
    rotation_day = (local_now - BATTLEFIELD_ANCHOR).days
    current_start = BATTLEFIELD_ANCHOR + timedelta(days=rotation_day)
    next_start = current_start + timedelta(days=1)
    _, current_full_name = battlefield_for_time(current_start)
    _, next_full_name = battlefield_for_time(next_start)
    return (
        "【每日战场轮换】\n"
        f"本轮（{current_start:%m-%d %H:%M}）："
        f"{current_full_name}\n"
        f"下轮（{next_start:%m-%d %H:%M}）："
        f"{next_full_name}"
    )


def strip_markup(value: str | None, limit: int = 240) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", html.unescape(value))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_feed(xml_text: str) -> list[FeedItem]:
    root = ElementTree.fromstring(xml_text)
    if _local_name(root.tag) == "feed":
        return _parse_atom(root)
    return _parse_rss(root)


def _parse_rss(root: ElementTree.Element) -> list[FeedItem]:
    result: list[FeedItem] = []
    for node in root.iter():
        if _local_name(node.tag) != "item":
            continue
        title = _child_text(node, "title")
        link = _child_text(node, "link")
        guid = _child_text(node, "guid")
        published = _normalize_date(
            _child_text(node, "pubDate") or _child_text(node, "date")
        )
        summary = strip_markup(
            _child_text(node, "description") or _child_text(node, "encoded")
        )
        result.append(_feed_item(guid, title, link, published, summary))
    return result


def _parse_atom(root: ElementTree.Element) -> list[FeedItem]:
    result: list[FeedItem] = []
    for node in root:
        if _local_name(node.tag) != "entry":
            continue
        title = _child_text(node, "title")
        item_id = _child_text(node, "id")
        link = ""
        for child in node:
            if _local_name(child.tag) == "link" and child.attrib.get("href"):
                if child.attrib.get("rel", "alternate") == "alternate":
                    link = child.attrib["href"]
                    break
        published = _normalize_date(
            _child_text(node, "published") or _child_text(node, "updated")
        )
        summary = strip_markup(
            _child_text(node, "summary") or _child_text(node, "content")
        )
        result.append(_feed_item(item_id, title, link, published, summary))
    return result


def _feed_item(
    item_id: str, title: str, link: str, published: str, summary: str
) -> FeedItem:
    stable_id = item_id or link
    if not stable_id:
        stable_id = hashlib.sha256(
            f"{title}\n{published}".encode("utf-8")
        ).hexdigest()
    return FeedItem(stable_id, strip_markup(title, 160), link.strip(), published, summary)


def _child_text(node: ElementTree.Element, name: str) -> str:
    for child in node:
        if _local_name(child.tag) == name:
            return "".join(child.itertext()).strip()
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _normalize_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=SHANGHAI_TZ)
        return parsed.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=SHANGHAI_TZ)
        return parsed.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value
