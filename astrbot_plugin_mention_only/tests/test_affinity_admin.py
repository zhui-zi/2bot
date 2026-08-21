from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


class _FilterApi:
    class EventMessageType:
        ALL = "all"
        GROUP_MESSAGE = "group"

    @staticmethod
    def event_message_type(*_args, **_kwargs):
        return lambda handler: handler

    @staticmethod
    def on_llm_request(*_args, **_kwargs):
        return lambda handler: handler

    @staticmethod
    def on_llm_response(*_args, **_kwargs):
        return lambda handler: handler

    @staticmethod
    def command(*_args, **_kwargs):
        return lambda handler: handler


class _FakeStar:
    def __init__(self, context) -> None:
        self.context = context
        self._kv: dict[str, object] = {}

    async def get_kv_data(self, key: str, default: object) -> object:
        return self._kv.get(key, default)

    async def put_kv_data(self, key: str, value: object) -> None:
        self._kv[key] = value


class _FakeAt:
    def __init__(self, qq: str) -> None:
        self.qq = qq


class _FakeReply:
    def __init__(self, sender_id: str = "", **_kwargs) -> None:
        self.sender_id = sender_id


class _FakePlain:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeEvent:
    def __init__(
        self,
        *,
        sender_id: str,
        group_id: str = "group-a",
        is_admin: bool = False,
        role: str = "",
    ) -> None:
        self._sender_id = sender_id
        self._group_id = group_id
        self._is_admin = is_admin
        self._messages: list[object] = []
        raw_data = {"group_id": group_id, "message_type": "group"}
        if role:
            raw_data["role"] = role
        raw = types.SimpleNamespace(raw_data=raw_data)
        self.message_obj = types.SimpleNamespace(raw_message=raw)

    def get_sender_id(self) -> str:
        return self._sender_id

    def get_group_id(self) -> str:
        return self._group_id

    def get_platform_name(self) -> str:
        return "aiocqhttp"

    def get_self_id(self) -> str:
        return "bot"

    def get_messages(self) -> list[object]:
        return self._messages

    def is_admin(self) -> bool:
        return self._is_admin

    def is_private_chat(self) -> bool:
        return not bool(self._group_id)

    @staticmethod
    def plain_result(text: str) -> str:
        return text


class AffinityAdminTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        module_names = (
            "astrbot",
            "astrbot.api",
            "astrbot.api.event",
            "astrbot.api.message_components",
            "astrbot.api.provider",
            "astrbot.api.star",
            "astrbot.core",
            "astrbot.core.message",
            "astrbot.core.message.message_event_result",
        )
        cls._original_modules = {
            name: sys.modules.get(name) for name in module_names
        }
        astrbot = types.ModuleType("astrbot")
        api = types.ModuleType("astrbot.api")
        api.AstrBotConfig = dict
        api.logger = types.SimpleNamespace(info=lambda *_args, **_kwargs: None)
        event = types.ModuleType("astrbot.api.event")
        event.AstrMessageEvent = object
        event.filter = _FilterApi
        components = types.ModuleType("astrbot.api.message_components")
        components.At = _FakeAt
        components.Plain = _FakePlain
        components.Reply = _FakeReply
        provider = types.ModuleType("astrbot.api.provider")
        provider.LLMResponse = object
        provider.ProviderRequest = object
        star = types.ModuleType("astrbot.api.star")
        star.Context = object
        star.Star = _FakeStar
        star.register = lambda *_args, **_kwargs: lambda value: value
        core = types.ModuleType("astrbot.core")
        message = types.ModuleType("astrbot.core.message")
        event_result = types.ModuleType(
            "astrbot.core.message.message_event_result"
        )
        event_result.MessageChain = list
        sys.modules.update(
            {
                "astrbot": astrbot,
                "astrbot.api": api,
                "astrbot.api.event": event,
                "astrbot.api.message_components": components,
                "astrbot.api.provider": provider,
                "astrbot.api.star": star,
                "astrbot.core": core,
                "astrbot.core.message": message,
                "astrbot.core.message.message_event_result": event_result,
            }
        )
        sys.modules.pop("astrbot_plugin_mention_only.main", None)
        cls.plugin_module = importlib.import_module(
            "astrbot_plugin_mention_only.main"
        )
        from astrbot_plugin_permissions.permission_core import (
            configure_permission_policy,
        )

        cls.configure_permission_policy = staticmethod(
            configure_permission_policy
        )

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.pop("astrbot_plugin_mention_only.main", None)
        for name, module in cls._original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    async def asyncSetUp(self) -> None:
        self.configure_permission_policy(bot_author_ids=["author"])
        self.plugin = self.plugin_module.MentionOnlyChat(
            object(),
            {"hidden_romance_enabled": True},
        )

    @staticmethod
    async def _results(generator) -> list[str]:
        return [item async for item in generator]

    async def test_verified_author_can_set_explicit_target_score(self) -> None:
        event = _FakeEvent(sender_id="author")
        results = await self._results(
            self.plugin.affinity_admin(event, "set", "target", "80.5")
        )
        self.assertIn("80.5/100", results[0])
        state = await self.plugin._load_affinity_state("aiocqhttp", "target")
        self.assertEqual(state.score, 80.5)

    async def test_verified_author_can_set_mentioned_target_score(self) -> None:
        event = _FakeEvent(sender_id="author")
        event._messages.append(_FakeAt("target"))
        results = await self._results(
            self.plugin.affinity_admin(event, "设置", "55")
        )
        self.assertIn("55.0/100", results[0])
        state = await self.plugin._load_affinity_state("aiocqhttp", "target")
        self.assertEqual(state.score, 55.0)

    async def test_other_privileged_roles_cannot_set_score(self) -> None:
        astrbot_admin = _FakeEvent(sender_id="admin", is_admin=True)
        results = await self._results(
            self.plugin.affinity_admin(
                astrbot_admin,
                "set",
                "target",
                "90",
            )
        )
        self.assertIn("仅机器人作者", results[0])

        group_admin = _FakeEvent(sender_id="manager", role="admin")
        results = await self._results(
            self.plugin.affinity_admin(
                group_admin,
                "set",
                "target",
                "90",
            )
        )
        self.assertIn("仅机器人作者", results[0])

    async def test_invalid_score_does_not_create_state(self) -> None:
        event = _FakeEvent(sender_id="author")
        results = await self._results(
            self.plugin.affinity_admin(event, "set", "target", "101")
        )
        self.assertIn("用法", results[0])
        state = await self.plugin._load_affinity_state("aiocqhttp", "target")
        self.assertEqual(state.score, 0)


if __name__ == "__main__":
    unittest.main()
