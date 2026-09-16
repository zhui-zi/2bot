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
        self.id = _kwargs.get("id", "")


class _FakePlain:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeChain:
    def __init__(self, chain) -> None:
        self.chain = chain


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
        cls._original_modules = {name: sys.modules.get(name) for name in module_names}
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
        event_result = types.ModuleType("astrbot.core.message.message_event_result")
        event_result.MessageChain = _FakeChain
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
        cls.plugin_module = importlib.import_module("astrbot_plugin_mention_only.main")
        from astrbot_plugin_permissions.permission_core import (
            configure_permission_policy,
        )

        cls.configure_permission_policy = staticmethod(configure_permission_policy)

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
        results = await self._results(self.plugin.affinity_admin(event, "设置", "55"))
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

    async def test_official_adapter_bot_marker_is_a_direct_trigger(self) -> None:
        event = _FakeEvent(sender_id="member")
        event.get_platform_name = lambda: "qq_official"
        event.get_self_id = lambda: "unknown_selfid"
        event._messages = [_FakeAt("qq_official")]
        self.assertTrue(self.plugin._targets_bot(event))
        event._messages = [_FakeAt("another-member")]
        self.assertFalse(self.plugin._targets_bot(event))

    async def test_official_marker_does_not_trigger_other_platforms(self) -> None:
        event = _FakeEvent(sender_id="member")
        event._messages = [_FakeAt("qq_official")]
        self.assertFalse(self.plugin._targets_bot(event))

    async def test_empty_reply_sender_does_not_target_unknown_bot(self) -> None:
        event = _FakeEvent(sender_id="member")
        event.get_self_id = lambda: ""
        event._messages = [_FakeReply("")]
        self.assertFalse(self.plugin._targets_bot(event))

    async def test_official_group_chat_response_carries_native_reference(self) -> None:
        event = _FakeEvent(sender_id="member")
        event.get_platform_name = lambda: "qq_official"
        event.message_obj.message_id = "message-a"

        async def send(send_func, payload, plain_text, stream=None):
            return payload

        event._send_with_markdown_fallback = send
        response = types.SimpleNamespace(result_chain=None, completion_text="完整回复")
        await self.plugin.quote_group_reply_target(event, response)
        self.assertEqual(response.result_chain.chain[0].id, "message-a")
        self.assertEqual(response.result_chain.chain[1].text, "完整回复")
        payload = await event._send_with_markdown_fallback(None, {}, "完整回复")
        self.assertEqual(payload["message_reference"]["message_id"], "message-a")

    async def test_official_reference_is_bound_before_streamed_response(self) -> None:
        self.plugin.config["hidden_affinity_enabled"] = False
        event = _FakeEvent(sender_id="member")
        event.get_platform_name = lambda: "qq_official"
        event.get_extra = lambda _key: None
        event._messages = [_FakeAt("qq_official")]
        event.message_obj.message_id = "message-a"

        async def send(send_func, payload, plain_text, stream=None):
            return payload

        event._send_with_markdown_fallback = send
        request = types.SimpleNamespace(system_prompt="", contexts=[])
        await self.plugin.require_direct_mention(event, request)
        payload = await event._send_with_markdown_fallback(None, {}, "完整回复")
        self.assertEqual(payload["message_reference"]["message_id"], "message-a")

    async def test_official_private_response_is_not_quoted(self) -> None:
        event = _FakeEvent(sender_id="member", group_id="")
        event.get_platform_name = lambda: "qq_official"
        event.message_obj.message_id = "message-a"
        response = types.SimpleNamespace(result_chain=None, completion_text="完整回复")
        await self.plugin.quote_group_reply_target(event, response)
        self.assertIsNone(response.result_chain)

    async def test_unsupported_official_adapter_shows_sender_name(self) -> None:
        event = _FakeEvent(sender_id="member")
        event.get_platform_name = lambda: "qq_official"
        event.get_sender_name = lambda: "Keita"
        event.message_obj.message_id = "message-a"
        response = types.SimpleNamespace(result_chain=None, completion_text="完整回复")
        await self.plugin.quote_group_reply_target(event, response)
        self.assertEqual(response.result_chain.chain[0].text, "回复 Keita：\n")
        self.assertEqual(response.result_chain.chain[1].text, "完整回复")

    async def test_disabled_quotes_leave_official_response_unchanged(self) -> None:
        self.plugin.config["quote_group_replies"] = False
        event = _FakeEvent(sender_id="member")
        event.get_platform_name = lambda: "qq_official"
        event.message_obj.message_id = "message-a"
        response = types.SimpleNamespace(result_chain=None, completion_text="完整回复")
        await self.plugin.quote_group_reply_target(event, response)
        self.assertIsNone(response.result_chain)


if __name__ == "__main__":
    unittest.main()
