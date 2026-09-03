from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Iterable

from .ff14_utils import SHANGHAI_TZ


HOUSING_SOURCE_URL = "https://house.ffxiv.cyou/"
LOTTERY_ANCHOR = datetime(2022, 8, 8, 23, 0, tzinfo=SHANGHAI_TZ)
APPLICATION_SECONDS = int(timedelta(days=5).total_seconds())
RESULTS_SECONDS = int(timedelta(days=4).total_seconds())
CYCLE_SECONDS = APPLICATION_SECONDS + RESULTS_SECONDS

AREA_NAMES = {
    0: "海雾村",
    1: "薰衣草苗圃",
    2: "高脚孤丘",
    3: "白银乡",
    4: "穹顶皓天",
}
SIZE_NAMES = {0: "S", 1: "M", 2: "L"}
REGION_NAMES = {0: "通用", 1: "部队", 2: "个人"}

SERVER_GROUPS: tuple[tuple[str, tuple[tuple[str, int], ...]], ...] = (
    (
        "陆行鸟",
        (
            ("红玉海", 1167),
            ("神意之地", 1081),
            ("拉诺西亚", 1042),
            ("幻影群岛", 1044),
            ("萌芽池", 1060),
            ("宇宙和音", 1173),
            ("沃仙曦染", 1174),
            ("晨曦王座", 1175),
        ),
    ),
    (
        "莫古力",
        (
            ("白银乡", 1172),
            ("白金幻象", 1076),
            ("神拳痕", 1171),
            ("潮风亭", 1170),
            ("旅人栈桥", 1113),
            ("拂晓之间", 1121),
            ("龙巢神殿", 1166),
            ("梦羽宝境", 1176),
        ),
    ),
    (
        "猫小胖",
        (
            ("紫水栈桥", 1043),
            ("延夏", 1169),
            ("静语庄园", 1106),
            ("摩杜纳", 1045),
            ("海猫茶屋", 1177),
            ("柔风海湾", 1178),
            ("琥珀原", 1179),
        ),
    ),
    (
        "豆豆柴",
        (
            ("水晶塔", 1192),
            ("银泪湖", 1183),
            ("太阳海岸", 1180),
            ("伊修加德", 1186),
            ("红茶川", 1201),
        ),
    ),
)
SERVERS = tuple(server for _group, servers in SERVER_GROUPS for server in servers)
SERVER_NAME_TO_ID = {name: server_id for name, server_id in SERVERS}
SERVER_ID_TO_NAME = {server_id: name for name, server_id in SERVERS}


@dataclass(frozen=True)
class HousingCriteria:
    server_ids: tuple[int, ...]
    sizes: frozenset[int]
    audiences: frozenset[str]


@dataclass(frozen=True)
class House:
    server_id: int
    area: int
    slot: int
    plot_id: int
    price: int
    size: int
    first_seen: int
    last_seen: int
    state: int
    participate: int
    winner: int
    end_time: int
    update_time: int
    purchase_type: int
    region_type: int
    inferred: bool = False


def lottery_cycle(now: datetime) -> tuple[str, int, int, int]:
    now_ts = int(now.astimezone(SHANGHAI_TZ).timestamp())
    anchor_ts = int(LOTTERY_ANCHOR.timestamp())
    cycle_index = math.floor((now_ts - anchor_ts) / CYCLE_SECONDS)
    start = anchor_ts + cycle_index * CYCLE_SECONDS
    application_end = start + APPLICATION_SECONDS
    state = 1 if now_ts < application_end else 2
    end_time = application_end if state == 1 else start + CYCLE_SECONDS
    return str(start), state, start, end_time


def housing_result_reminder_due(
    subscription: dict[str, Any],
    cycle_key: str,
    state: int,
) -> bool:
    return (
        bool(subscription.get("house"))
        and state == 2
        and subscription.get("house_result_cycle") != cycle_key
    )


def render_housing_result_reminder(result_end: int) -> str:
    end = datetime.fromtimestamp(result_end, SHANGHAI_TZ)
    return (
        "【国服房屋抽选结果】\n"
        "本轮抽选结果已公布，请及时登录游戏确认。\n"
        f"结果确认期截止：{end:%Y-%m-%d %H:%M}"
    )


def parse_house(payload: Any, now: datetime) -> House | None:
    if not isinstance(payload, dict):
        return None
    try:
        house = House(
            server_id=int(payload.get("Server", 0)),
            area=int(payload.get("Area", -1)),
            slot=int(payload.get("Slot", -1)),
            plot_id=int(payload.get("ID", 0)),
            price=int(payload.get("Price", 0)),
            size=int(payload.get("Size", -1)),
            first_seen=int(payload.get("FirstSeen", 0)),
            last_seen=int(payload.get("LastSeen", 0)),
            state=int(payload.get("State", 0)),
            participate=int(payload.get("Participate", 0)),
            winner=int(payload.get("Winner", 0)),
            end_time=int(payload.get("EndTime", 0)),
            update_time=int(payload.get("UpdateTime", 0)),
            purchase_type=int(payload.get("PurchaseType", 0)),
            region_type=int(payload.get("RegionType", 0)),
        )
    except (TypeError, ValueError, OverflowError):
        return None
    if (
        house.server_id not in SERVER_ID_TO_NAME
        or house.area not in AREA_NAMES
        or house.slot < 0
        or house.plot_id <= 0
        or house.size not in SIZE_NAMES
    ):
        return None

    reliable = bool(
        house.end_time
        and house.update_time
        and "Winner" in payload
        and house.state
        and "Participate" in payload
    )
    return _advance_reported_house(house, now) if reliable else _infer_house(house, now)


def _infer_house(house: House, now: datetime) -> House:
    now_ts = int(now.astimezone(SHANGHAI_TZ).timestamp())
    anchor_ts = int(LOTTERY_ANCHOR.timestamp())
    first_seen = house.first_seen or now_ts
    first_index = math.ceil((first_seen - anchor_ts) / CYCLE_SECONDS)
    first_start = anchor_ts + first_index * CYCLE_SECONDS
    if now_ts < first_start:
        return replace(house, state=3, end_time=first_start, inferred=True)

    cycle_index = math.floor((now_ts - first_start) / CYCLE_SECONDS)
    start = first_start + cycle_index * CYCLE_SECONDS
    application_end = start + APPLICATION_SECONDS
    if now_ts < application_end:
        return replace(house, state=1, end_time=application_end, inferred=True)
    return replace(
        house,
        state=2,
        end_time=start + CYCLE_SECONDS,
        inferred=True,
    )


def _advance_reported_house(house: House, now: datetime) -> House:
    now_ts = int(now.astimezone(SHANGHAI_TZ).timestamp())
    state = house.state
    end_time = house.end_time
    participate = house.participate
    winner = house.winner
    update_time = house.update_time
    while end_time and now_ts >= end_time:
        if state == 1:
            state = 2
            end_time += RESULTS_SECONDS
        elif state in {2, 3}:
            if state == 2:
                participate = -1
                winner = -1
                update_time = -1
            state = 1
            end_time += APPLICATION_SECONDS
        else:
            return _infer_house(house, now)
    return replace(
        house,
        state=state,
        end_time=end_time,
        participate=participate,
        winner=winner,
        update_time=update_time,
    )


def parse_housing_criteria(value: str) -> tuple[HousingCriteria | None, str]:
    text = str(value or "").strip()
    server_ids: list[int] = []
    for group_name, group_servers in SERVER_GROUPS:
        if group_name in text:
            server_ids.extend(server_id for _name, server_id in group_servers)
    for name, server_id in SERVERS:
        if name in text:
            server_ids.append(server_id)
    for token in re.findall(r"(?<!\d)\d{4}(?!\d)", text):
        server_id = int(token)
        if server_id in SERVER_ID_TO_NAME:
            server_ids.append(server_id)
    server_ids = list(dict.fromkeys(server_ids))
    if not server_ids:
        return None, "请至少指定一个国服服务器名称。"

    sizes: set[int] = set()
    compact = re.sub(r"\s+", "", text).upper()
    if re.search(r"(?:全部|所有|不限|全)(?:房型|户型|大小)", compact):
        sizes.update(SIZE_NAMES)
    for token in re.findall(r"(?<![A-Z])([SML])(?:型|房)?(?![A-Z])", compact):
        sizes.add({"S": 0, "M": 1, "L": 2}[token])
    if re.search(r"小(?:型|房|屋)", compact):
        sizes.add(0)
    if re.search(r"中(?:型|房|屋)", compact):
        sizes.add(1)
    if re.search(r"大(?:型|房|屋)", compact):
        sizes.add(2)
    if not sizes:
        sizes.update(SIZE_NAMES)

    audiences: set[str] = set()
    if re.search(r"个人|(?<![A-Z])PERSONAL(?![A-Z])", text, re.I):
        audiences.add("personal")
    if re.search(r"部队|公会|(?<![A-Z])FC(?![A-Z])", text, re.I):
        audiences.add("fc")
    if re.search(r"通用|不限购|无限制|(?<![A-Z])SHARED(?![A-Z])", text, re.I):
        audiences.add("shared")
    if re.search(
        r"(?:全部|所有|不限)(?:用途|资格|购买限制)|(?<![A-Z])ALL(?![A-Z])",
        text,
        re.I,
    ):
        audiences.update({"personal", "fc"})
    if not audiences:
        audiences.update({"personal", "fc"})

    order = {server_id: index for index, (_name, server_id) in enumerate(SERVERS)}
    return (
        HousingCriteria(
            tuple(sorted(server_ids, key=order.__getitem__)),
            frozenset(sizes),
            frozenset(audiences),
        ),
        "",
    )


def criteria_from_subscription(subscription: dict[str, Any]) -> HousingCriteria | None:
    try:
        server_ids = tuple(
            server_id
            for server_id in (int(value) for value in subscription.get("house_servers", []))
            if server_id in SERVER_ID_TO_NAME
        )
        sizes = frozenset(
            size
            for size in (int(value) for value in subscription.get("house_sizes", []))
            if size in SIZE_NAMES
        )
        audiences = frozenset(
            value
            for value in subscription.get("house_audiences", [])
            if value in {"personal", "fc", "shared"}
        )
    except (TypeError, ValueError):
        return None
    if not server_ids:
        return None
    return HousingCriteria(
        server_ids,
        sizes or frozenset(SIZE_NAMES),
        audiences or frozenset({"personal", "fc"}),
    )


def house_matches(
    house: House,
    criteria: HousingCriteria,
    now: datetime,
    stale_seconds: int,
) -> bool:
    if (
        house.server_id not in criteria.server_ids
        or house.purchase_type != 2
        or house.state != 1
        or house.size not in criteria.sizes
    ):
        return False
    now_ts = int(now.astimezone(SHANGHAI_TZ).timestamp())
    if house.last_seen <= 0 or now_ts - house.last_seen > stale_seconds:
        return False
    allowed_regions: set[int] = set()
    if "personal" in criteria.audiences:
        allowed_regions.update({0, 2})
    if "fc" in criteria.audiences:
        allowed_regions.update({0, 1})
    if "shared" in criteria.audiences:
        allowed_regions.add(0)
    return house.region_type in allowed_regions


def criteria_text(criteria: HousingCriteria) -> str:
    servers = "、".join(SERVER_ID_TO_NAME[value] for value in criteria.server_ids)
    sizes = "/".join(SIZE_NAMES[value] for value in sorted(criteria.sizes))
    if criteria.audiences == {"shared"}:
        audience = "仅通用"
    elif "personal" in criteria.audiences and "fc" in criteria.audiences:
        audience = "个人/部队均可抽"
    elif "personal" in criteria.audiences:
        audience = "个人可抽（含通用）"
    elif "fc" in criteria.audiences:
        audience = "部队可抽（含通用）"
    else:
        audience = "通用"
    return f"服务器：{servers}；房型：{sizes}；资格：{audience}"


def render_housing_message(
    server_id: int,
    houses: Iterable[House],
    criteria: HousingCriteria,
    *,
    max_items: int,
) -> str:
    ordered = sorted(
        houses,
        key=lambda item: (-item.size, item.area, item.slot, item.plot_id),
    )
    server_name = SERVER_ID_TO_NAME[server_id]
    lines = ["【国服空闲房区｜本轮申请】", server_name]
    if ordered:
        end = datetime.fromtimestamp(ordered[0].end_time, SHANGHAI_TZ)
        lines.append(f"申请截止：{end:%Y-%m-%d %H:%M}")
    lines.append(criteria_text(replace(criteria, server_ids=(server_id,))))
    lines.append(f"符合条件：{len(ordered)} 套")
    for house in ordered[: max(1, max_items)]:
        inferred = "（推测）" if house.inferred else ""
        lines.append(
            f"{SIZE_NAMES[house.size]}｜{AREA_NAMES[house.area]} "
            f"{house.slot + 1}区 {house.plot_id}号｜"
            f"{REGION_NAMES.get(house.region_type, '未知')}｜"
            f"{house.price:,}金币{inferred}"
        )
    omitted = len(ordered) - max(1, max_items)
    if omitted > 0:
        lines.append(f"另有 {omitted} 套未展开，请前往数据源查看。")
    if not ordered:
        lines.append("本轮暂未发现符合筛选条件且数据仍在时效范围内的房屋。")
    lines.extend(("数据来自艾欧泽亚售楼中心，仅供参考：", HOUSING_SOURCE_URL))
    return "\n".join(lines)
