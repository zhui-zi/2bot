from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from typing import Any

import httpx
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.star.filter.command import GreedyStr
try:
    from data.plugins.astrbot_plugin_permissions.permission_core import (
        PERMISSION_GROUP_MANAGER,
        resolve_event_permission,
    )
except ImportError:
    from astrbot_plugin_permissions.permission_core import (
        PERMISSION_GROUP_MANAGER,
        resolve_event_permission,
    )

from .ff14_utils import (
    FeedItem,
    SHANGHAI_TZ,
    battlefield_rotation_text,
    normalize_scene,
    normalize_subscription,
    parse_feed,
    resolve_qq_scene,
)
from .housing import (
    HousingCriteria,
    criteria_from_subscription,
    criteria_text,
    house_matches,
    housing_result_reminder_due,
    lottery_cycle,
    parse_house,
    parse_housing_criteria,
    render_housing_message,
    render_housing_result_reminder,
)


STATE_KEY = "state_v1"


@register(
    "ff14_cn_push",
    "keita",
    "QQ Official and SnowLuma FF14 CN notifications.",
    "1.3.3",
)
class FF14CnPush(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._state: dict[str, Any] = {"subscriptions": {}}
        self._state_lock = asyncio.Lock()
        self._ready = asyncio.Event()
        self._stopping = asyncio.Event()
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=float(config.get("request_timeout_seconds", 20)),
            headers={
                "User-Agent": (
                    "AstrBot-FF14-CN-Push/1.2 "
                    "(https://github.com/zhui-zi/2bot)"
                )
            },
        )
        self._task = asyncio.create_task(self._run())

    @filter.command("ff14push")
    async def ff14push(
        self,
        event: AstrMessageEvent,
        feature: str = "status",
        action: str = "",
        details: GreedyStr = "",
    ):
        """Manage FF14 CN group or private notifications."""
        await self._ensure_state()
        scene = self._event_scene(event)
        if not scene:
            yield event.plain_result(
                "该命令只能在 QQ 官方机器人或 SnowLuma 的群聊或私聊中使用。"
            )
            return
        target_id = self._target_id(event, scene)
        if not target_id:
            yield event.plain_result("无法识别当前 QQ 会话，请稍后重试。")
            return

        feature = feature.lower().strip()
        action = action.lower().strip()
        if feature in {"status", "状态"}:
            yield event.plain_result(self._status_text(event))
            return
        if feature in {"today", "今日", "战场"} and not action:
            yield event.plain_result(self._battlefield_text(datetime.now(SHANGHAI_TZ)))
            return
        if feature in {"house", "housing", "房屋", "房区", "空房"}:
            async for result in self._handle_housing_command(
                event,
                scene,
                target_id,
                action,
                str(details),
            ):
                yield result
            return

        normalized_feature = self._normalize_feature(feature)
        normalized_action = self._normalize_action(action)
        if not normalized_feature or not normalized_action:
            yield event.plain_result(
                "用法：/ff14push news on|off，/ff14push pvp on|off，"
                "/ff14push house on <服务器> [S|M|L] [个人|部队|通用|全部]，"
                "/ff14push house off|now，/ff14push status，/ff14push today"
            )
            return
        if scene == "group" and not self._is_manager(event):
            yield event.plain_result(
                "权限不足：仅机器人作者、AstrBot 管理员或当前群群主/管理员"
                "可修改推送设置。"
            )
            return

        umo = event.unified_msg_origin
        async with self._state_lock:
            subscription = self._subscription(umo, target_id, scene)
            enabled = normalized_action == "on"
            subscription[normalized_feature] = enabled
            if normalized_feature == "news" and enabled:
                await self._initialize_news(subscription)
            await self._save_state()

        label = "国服新闻" if normalized_feature == "news" else "每日战场"
        state_label = "已开启" if enabled else "已关闭"
        extra = ""
        if normalized_feature == "pvp" and enabled:
            extra = "\n" + self._battlefield_text(datetime.now(SHANGHAI_TZ))
        yield event.plain_result(f"{label}推送{state_label}。{extra}")

    async def _run(self) -> None:
        try:
            await self._ensure_state()
            delay = max(0, int(self.config.get("startup_delay_seconds", 10)))
            await asyncio.sleep(delay)
            last_news_poll = 0.0
            last_house_poll = 0.0
            loop = asyncio.get_running_loop()
            while not self._stopping.is_set():
                now = datetime.now(SHANGHAI_TZ)
                news_interval = max(
                    60,
                    int(self.config.get("news_poll_seconds", 300)),
                )
                if loop.time() - last_news_poll >= news_interval:
                    await self._poll_news()
                    last_news_poll = loop.time()
                house_interval = max(
                    300,
                    int(self.config.get("housing_poll_seconds", 600)),
                )
                if loop.time() - last_house_poll >= house_interval:
                    await self._poll_housing(now)
                    last_house_poll = loop.time()
                await self._push_battlefield_if_due(now)
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=30)
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("FF14 CN push scheduler stopped unexpectedly")

    async def _ensure_state(self) -> None:
        if self._ready.is_set():
            return
        async with self._state_lock:
            if self._ready.is_set():
                return
            loaded = await self.get_kv_data(STATE_KEY, {"subscriptions": {}})
            if isinstance(loaded, dict) and isinstance(loaded.get("subscriptions"), dict):
                self._state = loaded
            self._ready.set()

    async def _save_state(self) -> None:
        await self.put_kv_data(STATE_KEY, self._state)

    def _subscription(self, umo: str, target_id: str, scene: str) -> dict[str, Any]:
        subscriptions = self._state.setdefault("subscriptions", {})
        subscription = subscriptions.get(umo)
        normalized = normalize_subscription(subscription, target_id, scene)
        subscriptions[umo] = normalized
        return normalized

    async def _initialize_news(self, subscription: dict[str, Any]) -> None:
        if subscription.get("news_initialized"):
            return
        try:
            items = await self._fetch_news()
        except Exception as exc:
            logger.warning("Unable to seed FF14 news feed: %s", exc)
            return
        subscription["news_seen"] = [item.item_id for item in items[:100]]
        subscription["news_initialized"] = True

    async def _poll_news(self) -> None:
        await self._ensure_state()
        async with self._state_lock:
            targets = [
                (umo, subscription)
                for umo, subscription in self._state.get("subscriptions", {}).items()
                if subscription.get("news")
            ]
        if not targets:
            return
        try:
            items = await self._fetch_news()
        except Exception as exc:
            logger.warning("Unable to fetch FF14 news feed: %s", exc)
            return

        changed = False
        max_items = max(1, min(10, int(self.config.get("max_news_per_poll", 5))))
        for umo, subscription in targets:
            async with self._state_lock:
                if not subscription.get("news_initialized"):
                    subscription["news_seen"] = [item.item_id for item in items[:100]]
                    subscription["news_initialized"] = True
                    changed = True
                    continue
                seen = set(subscription.get("news_seen", []))
            unseen = [item for item in items if item.item_id not in seen]
            if len(unseen) > max_items:
                seen.update(item.item_id for item in unseen[max_items:])
                changed = True
            for item in reversed(unseen[:max_items]):
                try:
                    await self._send(
                        umo,
                        self._news_text(item),
                        normalize_scene(subscription.get("scene")),
                    )
                except Exception as exc:
                    logger.warning("Unable to send FF14 news to %s: %s", umo, exc)
                    break
                seen.add(item.item_id)
                changed = True
            async with self._state_lock:
                ordered_ids = [item.item_id for item in items if item.item_id in seen]
                older_ids = [
                    item_id
                    for item_id in subscription.get("news_seen", [])
                    if item_id in seen and item_id not in ordered_ids
                ]
                subscription["news_seen"] = (ordered_ids + older_ids)[:100]
        if changed:
            async with self._state_lock:
                await self._save_state()

    async def _fetch_news(self) -> list[FeedItem]:
        url = str(self.config.get("rss_url", "http://rsshub:1200/ff14/zh/all"))
        response = await self._client.get(url)
        response.raise_for_status()
        return parse_feed(response.text)

    async def _handle_housing_command(
        self,
        event: AstrMessageEvent,
        scene: str,
        target_id: str,
        action: str,
        details: str,
    ):
        normalized_action = self._normalize_action(action)
        if action.lower().strip() in {"now", "current", "当前", "本轮", "查询"}:
            subscription = self._state.get("subscriptions", {}).get(
                event.unified_msg_origin,
                {},
            )
            criteria = criteria_from_subscription(subscription)
            if details.strip():
                criteria, error = parse_housing_criteria(details)
                if error:
                    yield event.plain_result(error)
                    return
            if criteria is None:
                yield event.plain_result(
                    "当前会话尚未配置房屋筛选。请先使用 "
                    "/ff14push house on <服务器> [S|M|L] [个人|部队|通用|全部]。"
                )
                return
            async for result in self._current_housing_results(event, criteria):
                yield result
            return

        if normalized_action not in {"on", "off"}:
            yield event.plain_result(
                "用法：/ff14push house on <服务器> [S|M|L] "
                "[个人|部队|通用|全部]，或 /ff14push house off|now"
            )
            return
        if scene == "group" and not self._is_manager(event):
            yield event.plain_result(
                "权限不足：仅机器人作者、AstrBot 管理员或当前群群主/管理员"
                "可修改推送设置。"
            )
            return

        umo = event.unified_msg_origin
        if normalized_action == "off":
            async with self._state_lock:
                subscription = self._subscription(umo, target_id, scene)
                subscription["house"] = False
                await self._save_state()
            yield event.plain_result("国服空闲房区推送已关闭。")
            return

        criteria, error = parse_housing_criteria(details)
        if error or criteria is None:
            yield event.plain_result(error)
            return
        cycle_key, state, _start, _end = lottery_cycle(datetime.now(SHANGHAI_TZ))
        async with self._state_lock:
            subscription = self._subscription(umo, target_id, scene)
            subscription["house"] = True
            subscription["house_servers"] = list(criteria.server_ids)
            subscription["house_sizes"] = sorted(criteria.sizes)
            subscription["house_audiences"] = sorted(criteria.audiences)
            subscription["house_server_cycles"] = {
                str(server_id): cycle_key for server_id in criteria.server_ids
            }
            if state == 2:
                subscription["house_result_cycle"] = cycle_key
            await self._save_state()
        yield event.plain_result(
            "国服空闲房区推送已开启。\n"
            + criteria_text(criteria)
            + "\n将在下一轮申请期开始后推送；使用 /ff14push house now 可立即查询。"
        )

    async def _current_housing_results(
        self,
        event: AstrMessageEvent,
        criteria: HousingCriteria,
    ):
        now = datetime.now(SHANGHAI_TZ)
        for server_id in criteria.server_ids:
            try:
                houses, _updated_at = await self._fetch_houses(server_id, now)
            except Exception as exc:
                logger.warning("Unable to fetch housing data for %s: %s", server_id, exc)
                yield event.plain_result(f"服务器 {server_id} 的房屋数据暂时获取失败。")
                continue
            yield event.plain_result(
                self._housing_text(server_id, houses, criteria, now)
            )

    async def _poll_housing(self, now: datetime) -> None:
        await self._ensure_state()
        cycle_key, state, cycle_start, cycle_end = lottery_cycle(now)
        if state == 2:
            await self._push_housing_result_if_due(cycle_key, cycle_end)
            return
        if state != 1:
            return
        async with self._state_lock:
            targets: list[tuple[str, dict[str, Any], HousingCriteria, list[int]]] = []
            for umo, subscription in self._state.get("subscriptions", {}).items():
                if not subscription.get("house"):
                    continue
                criteria = criteria_from_subscription(subscription)
                if criteria is None:
                    continue
                sent_cycles = subscription.get("house_server_cycles", {})
                pending = [
                    server_id
                    for server_id in criteria.server_ids
                    if sent_cycles.get(str(server_id)) != cycle_key
                ]
                if pending:
                    targets.append((umo, subscription, criteria, pending))
        if not targets:
            return

        server_ids = sorted(
            {server_id for _umo, _sub, _criteria, pending in targets for server_id in pending}
        )
        fetched: dict[int, list[Any]] = {}
        for server_id in server_ids:
            try:
                houses, updated_at = await self._fetch_houses(server_id, now)
                if updated_at < cycle_start:
                    logger.info(
                        "Housing data for %s has not completed a new-cycle refresh.",
                        server_id,
                    )
                    continue
                fetched[server_id] = houses
            except Exception as exc:
                logger.warning("Unable to fetch housing data for %s: %s", server_id, exc)

        for umo, subscription, criteria, pending in targets:
            for server_id in pending:
                if server_id not in fetched:
                    continue
                try:
                    await self._send(
                        umo,
                        self._housing_text(
                            server_id,
                            fetched[server_id],
                            criteria,
                            now,
                        ),
                        normalize_scene(subscription.get("scene")),
                    )
                except Exception as exc:
                    logger.warning(
                        "Unable to send housing update to %s for %s: %s",
                        umo,
                        server_id,
                        exc,
                    )
                    continue
                async with self._state_lock:
                    cycles = subscription.setdefault("house_server_cycles", {})
                    cycles[str(server_id)] = cycle_key
                    await self._save_state()

    async def _push_housing_result_if_due(
        self,
        cycle_key: str,
        result_end: int,
    ) -> None:
        async with self._state_lock:
            targets = [
                (umo, subscription)
                for umo, subscription in self._state.get("subscriptions", {}).items()
                if housing_result_reminder_due(subscription, cycle_key, 2)
            ]
        for umo, subscription in targets:
            try:
                await self._send(
                    umo,
                    render_housing_result_reminder(result_end),
                    normalize_scene(subscription.get("scene")),
                )
            except Exception as exc:
                logger.warning(
                    "Unable to send housing result reminder to %s: %s",
                    umo,
                    exc,
                )
                continue
            async with self._state_lock:
                subscription["house_result_cycle"] = cycle_key
                await self._save_state()

    async def _fetch_houses(
        self,
        server_id: int,
        now: datetime,
    ) -> tuple[list[Any], int]:
        base_url = str(
            self.config.get("housing_api_base_url", "https://house.ffxiv.cyou/api")
        ).rstrip("/")
        cache_key = int(now.timestamp() // 60)
        sales_response, update_response = await asyncio.gather(
            self._client.get(
                f"{base_url}/sales",
                params={"server": server_id, "ts": cache_key},
            ),
            self._client.get(
                f"{base_url}/update_time",
                params={"server": server_id, "ts": cache_key},
            ),
        )
        sales_response.raise_for_status()
        update_response.raise_for_status()
        payload = sales_response.json()
        if not isinstance(payload, list):
            raise ValueError("housing API returned a non-list response")
        update_payload = update_response.json()
        if not isinstance(update_payload, dict):
            raise ValueError("housing update API returned a non-object response")
        try:
            updated_at = int(update_payload.get("Time", 0))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("housing update API returned an invalid timestamp") from exc
        return (
            [
                house
                for item in payload
                if (house := parse_house(item, now)) is not None
            ],
            updated_at,
        )

    def _housing_text(
        self,
        server_id: int,
        houses: list[Any],
        criteria: HousingCriteria,
        now: datetime,
    ) -> str:
        stale_seconds = max(
            3600,
            min(
                7 * 86400,
                int(self.config.get("housing_stale_hours", 24)) * 3600,
            ),
        )
        matches = [
            house
            for house in houses
            if house_matches(house, criteria, now, stale_seconds)
        ]
        max_items = max(
            1,
            min(100, int(self.config.get("max_houses_per_message", 30))),
        )
        return render_housing_message(
            server_id,
            matches,
            criteria,
            max_items=max_items,
        )

    async def _push_battlefield_if_due(self, now: datetime) -> None:
        push_hour = max(0, min(23, int(self.config.get("battlefield_hour", 23))))
        if now.hour < push_hour:
            return
        date_key = now.date().isoformat()
        async with self._state_lock:
            targets = [
                (umo, subscription)
                for umo, subscription in self._state.get("subscriptions", {}).items()
                if subscription.get("pvp")
                and subscription.get("battlefield_last_date") != date_key
            ]
        changed = False
        for umo, subscription in targets:
            try:
                await self._send(
                    umo,
                    self._battlefield_text(now),
                    normalize_scene(subscription.get("scene")),
                )
            except Exception as exc:
                logger.warning("Unable to send battlefield rotation to %s: %s", umo, exc)
                continue
            async with self._state_lock:
                subscription["battlefield_last_date"] = date_key
            changed = True
        if changed:
            async with self._state_lock:
                await self._save_state()

    def _status_text(self, event: AstrMessageEvent) -> str:
        subscription = self._state.get("subscriptions", {}).get(
            event.unified_msg_origin, {}
        )
        news = "开启" if subscription.get("news") else "关闭"
        pvp = "开启" if subscription.get("pvp") else "关闭"
        housing = "关闭"
        if subscription.get("house"):
            criteria = criteria_from_subscription(subscription)
            housing = "开启" + (f"\n  {criteria_text(criteria)}" if criteria else "（配置无效）")
        scope = "当前私聊" if self._event_scene(event) == "friend" else "当前群聊"
        return (
            f"{scope}订阅\nFF14 国服新闻：{news}\n"
            f"每日 23:00 战场：{pvp}\n国服空闲房区：{housing}"
        )

    async def _send(self, umo: str, text: str, scene: str) -> None:
        self._restore_qq_scene(umo, scene)
        sent = await self.context.send_message(umo, MessageChain().message(text))
        if not sent:
            raise RuntimeError("platform rejected proactive message")

    def _restore_qq_scene(self, umo: str, scene: str) -> None:
        try:
            platform_id, _message_type, session_id = umo.split(":", 2)
        except ValueError:
            return
        platform_manager = getattr(self.context, "platform_manager", None)
        for platform in getattr(platform_manager, "platform_insts", []):
            meta = platform.meta()
            if meta.id != platform_id or meta.name != "qq_official":
                continue
            remember_scene = getattr(platform, "remember_session_scene", None)
            if callable(remember_scene):
                remember_scene(session_id, normalize_scene(scene))
            return

    @staticmethod
    def _event_scene(event: AstrMessageEvent) -> str:
        platform_name = str(event.get_platform_name() or "")
        is_group = bool(event.get_group_id())
        if platform_name.strip().lower() == "qq_official":
            is_group = is_group or FF14CnPush._is_qq_group(event)
        return resolve_qq_scene(
            platform_name,
            event.is_private_chat(),
            is_group,
        )

    @staticmethod
    def _target_id(event: AstrMessageEvent, scene: str) -> str:
        if scene == "group":
            return str(event.get_group_id() or "").strip()
        sender_id = str(event.get_sender_id() or "").strip()
        if sender_id:
            return sender_id
        parts = str(event.unified_msg_origin).split(":", 2)
        return parts[2] if len(parts) == 3 else ""

    def _is_manager(self, event: AstrMessageEvent) -> bool:
        return resolve_event_permission(event).level >= PERMISSION_GROUP_MANAGER

    @staticmethod
    def _is_qq_group(event: AstrMessageEvent) -> bool:
        raw_message = getattr(event.message_obj, "raw_message", None)
        raw = FF14CnPush._raw_data(event)
        return bool(
            (isinstance(raw, dict) and raw.get("group_openid"))
            or (
                raw_message
                and "groupmessage" in type(raw_message).__name__.lower()
            )
        )

    @staticmethod
    def _raw_data(event: AstrMessageEvent) -> Any:
        raw_message = getattr(event.message_obj, "raw_message", None)
        return getattr(raw_message, "raw_data", raw_message)

    @staticmethod
    def _normalize_feature(value: str) -> str:
        if value in {"news", "新闻", "资讯"}:
            return "news"
        if value in {"pvp", "battlefield", "战场"}:
            return "pvp"
        if value in {"house", "housing", "房屋", "房区", "空房"}:
            return "house"
        return ""

    @staticmethod
    def _normalize_action(value: str) -> str:
        if value in {"on", "enable", "开启", "开"}:
            return "on"
        if value in {"off", "disable", "关闭", "关"}:
            return "off"
        return ""

    @staticmethod
    def _news_text(item: FeedItem) -> str:
        parts = ["【FF14 国服资讯】", item.title]
        if item.published:
            parts.append(item.published)
        if item.summary:
            parts.append(item.summary)
        if item.link:
            parts.append(item.link)
        return "\n".join(parts)

    @staticmethod
    def _battlefield_text(now: datetime) -> str:
        return battlefield_rotation_text(now)

    async def terminate(self) -> None:
        self._stopping.set()
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        await self._client.aclose()
