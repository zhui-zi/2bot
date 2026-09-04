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

    @staticmethod
    def event_message_type(*_args, **_kwargs):
        return lambda handler: handler

    @staticmethod
    def on_llm_request(*_args, **_kwargs):
        return lambda handler: handler

    @staticmethod
    def command(*_args, **_kwargs):
        return lambda handler: handler


class _FakeStar:
    def __init__(self, _context) -> None:
        self.context = _context
        self._kv: dict[str, object] = {}

    async def get_kv_data(self, key: str, default: object) -> object:
        return self._kv.get(key, default)

    async def put_kv_data(self, key: str, value: object) -> None:
        self._kv[key] = value


class _FakeAt:
    def __init__(self, qq: str) -> None:
        self.qq = qq


class _FakeReply:
    def __init__(self, sender_id: str) -> None:
        self.sender_id = sender_id


class _FakeEvent:
    def __init__(
        self,
        *,
        sender_id: str,
        group_id: str,
        message: str,
        direct: bool = True,
    ) -> None:
        self._sender_id = sender_id
        self._group_id = group_id
        self._message = message
        self.is_at_or_wake_command = direct
        self._messages: list[object] = []
        self._extra: dict[str, object] = {}
        raw = types.SimpleNamespace(
            raw_data={"group_id": group_id, "message_type": "group"}
            if group_id
            else {"message_type": "private"}
        )
        self.message_obj = types.SimpleNamespace(raw_message=raw)

    def get_sender_id(self) -> str:
        return self._sender_id

    def get_group_id(self) -> str:
        return self._group_id

    def get_platform_name(self) -> str:
        return "aiocqhttp"

    def get_message_str(self) -> str:
        return self._message

    def get_self_id(self) -> str:
        return "bot"

    def get_messages(self) -> list[object]:
        return self._messages

    def is_admin(self) -> bool:
        return False

    def is_private_chat(self) -> bool:
        return not bool(self._group_id)

    def set_extra(self, key: str, value: object) -> None:
        self._extra[key] = value

    def get_extra(self, key: str) -> object:
        return self._extra.get(key)

    @staticmethod
    def plain_result(text: str) -> str:
        return text


class _FakeContext:
    def __init__(self) -> None:
        self.responses: list[str] = []
        self.calls: list[dict[str, object]] = []

    async def llm_generate(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise RuntimeError("missing fake response")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return types.SimpleNamespace(completion_text=response)


class GroupNsfwPluginTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_modules = {
            name: sys.modules.get(name)
            for name in (
                "astrbot",
                "astrbot.api",
                "astrbot.api.event",
                "astrbot.api.message_components",
                "astrbot.api.provider",
                "astrbot.api.star",
            )
        }
        astrbot = types.ModuleType("astrbot")
        api = types.ModuleType("astrbot.api")
        api.AstrBotConfig = dict
        api.logger = types.SimpleNamespace(
            info=lambda *_args, **_kwargs: None,
            warning=lambda *_args, **_kwargs: None,
        )
        event = types.ModuleType("astrbot.api.event")
        event.AstrMessageEvent = object
        event.filter = _FilterApi
        message_components = types.ModuleType("astrbot.api.message_components")
        message_components.At = _FakeAt
        message_components.Reply = _FakeReply
        provider = types.ModuleType("astrbot.api.provider")
        provider.ProviderRequest = object
        star = types.ModuleType("astrbot.api.star")
        star.Context = object
        star.Star = _FakeStar
        star.register = lambda *_args, **_kwargs: lambda value: value
        sys.modules.update(
            {
                "astrbot": astrbot,
                "astrbot.api": api,
                "astrbot.api.event": event,
                "astrbot.api.message_components": message_components,
                "astrbot.api.provider": provider,
                "astrbot.api.star": star,
            }
        )
        sys.modules.pop("astrbot_plugin_nsfw_unlock.main", None)
        cls.plugin_module = importlib.import_module("astrbot_plugin_nsfw_unlock.main")
        from astrbot_plugin_permissions.permission_core import (
            configure_permission_policy,
        )

        cls.configure_permission_policy = staticmethod(configure_permission_policy)

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.pop("astrbot_plugin_nsfw_unlock.main", None)
        for name, module in cls._original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    async def asyncSetUp(self) -> None:
        self.configure_permission_policy(bot_author_ids=["author"])
        self.context = _FakeContext()
        self.plugin = self.plugin_module.GroupNsfwUnlock(
            self.context,
            {
                "nsfw_prompt_prefix": "Custom prefix.",
                "nsfw_prompt_suffix": "Custom suffix.",
                "adult_classifier_enabled": True,
                "adult_classifier_provider_id": "deepseek_v4_flash",
            },
        )

    @staticmethod
    async def _results(generator) -> list[str]:
        return [item async for item in generator]

    async def test_only_author_can_change_current_group_state(self) -> None:
        author = _FakeEvent(sender_id="author", group_id="group-a", message="/nsfw on")
        result = await self._results(self.plugin.manage_nsfw(author, "on"))
        self.assertIn("已开启", result[0])

        member = _FakeEvent(sender_id="member", group_id="group-a", message="/nsfw off")
        result = await self._results(self.plugin.manage_nsfw(member, "off"))
        self.assertIn("权限不足", result[0])
        self.assertTrue(await self.plugin._is_enabled("aiocqhttp", "group-a"))
        self.assertFalse(await self.plugin._is_enabled("aiocqhttp", "group-b"))

    async def test_private_author_cannot_enable_a_group(self) -> None:
        private = _FakeEvent(sender_id="author", group_id="", message="/nsfw on")
        result = await self._results(self.plugin.manage_nsfw(private, "on"))
        self.assertIn("只能在群聊", result[0])

    async def test_enabled_group_injects_only_on_adult_turns(self) -> None:
        author = _FakeEvent(sender_id="author", group_id="group-a", message="/nsfw on")
        await self._results(self.plugin.manage_nsfw(author, "on"))

        adult_event = _FakeEvent(
            sender_id="member",
            group_id="group-a",
            message="讨论成年人的 NSFW 写作",
        )
        await self.plugin.mark_adult_turn(adult_event)
        adult_request = types.SimpleNamespace(
            prompt=adult_event.get_message_str(),
            contexts=[],
            system_prompt="Persona",
        )
        await self.plugin.prepare_adult_turn(adult_event, adult_request)
        adult_event.set_extra("_mention_only_relationship_stage", "trusted")
        await self.plugin.inject_adult_prompt(adult_event, adult_request)
        self.assertIn("[Group adult-content mode]", adult_request.system_prompt)
        self.assertIn("current relationship stage is trusted", adult_request.system_prompt)
        self.assertTrue(
            adult_request.system_prompt.startswith(
                "[Author-configured NSFW prefix]\nCustom prefix."
            )
        )
        self.assertLess(
            adult_request.system_prompt.index("Custom prefix."),
            adult_request.system_prompt.index("Persona"),
        )
        self.assertTrue(
            adult_request.system_prompt.endswith(
                "[Author-configured NSFW suffix]\nCustom suffix."
            )
        )

        ordinary_event = _FakeEvent(
            sender_id="member",
            group_id="group-a",
            message="今晚打什么副本？",
        )
        ordinary_request = types.SimpleNamespace(
            prompt=ordinary_event.get_message_str(),
            contexts=[],
            system_prompt="Persona",
        )
        await self.plugin.prepare_adult_turn(ordinary_event, ordinary_request)
        await self.plugin.inject_adult_prompt(ordinary_event, ordinary_request)
        self.assertEqual(ordinary_request.system_prompt, "Persona")

    async def test_short_continuation_is_prepared_before_final_injection(self) -> None:
        author = _FakeEvent(sender_id="author", group_id="group-a", message="/nsfw on")
        await self._results(self.plugin.manage_nsfw(author, "on"))
        continuation = _FakeEvent(
            sender_id="member",
            group_id="group-a",
            message="继续",
        )
        request = types.SimpleNamespace(
            prompt="继续",
            contexts=[{"role": "user", "content": "写一段成年恋人的床戏"}],
            system_prompt="Persona",
        )
        await self.plugin.prepare_adult_turn(continuation, request)
        self.assertEqual(
            continuation.get_extra("_nsfw_mode_active"),
            "adult_content",
        )
        await self.plugin.inject_adult_prompt(continuation, request)
        self.assertIn("[Group adult-content mode]", request.system_prompt)

    async def test_flash_classifies_unmatched_direct_messages_and_caches_result(self) -> None:
        author = _FakeEvent(sender_id="author", group_id="group-a", message="/nsfw on")
        await self._results(self.plugin.manage_nsfw(author, "on"))
        self.context.responses.append('{"adult": true, "confidence": 0.93}')

        first = _FakeEvent(
            sender_id="member",
            group_id="group-a",
            message="这个隐晦说法你懂的",
        )
        await self.plugin.mark_adult_turn(first)
        self.assertEqual(first.get_extra("_nsfw_mode_active"), "adult_content")
        self.assertEqual(len(self.context.calls), 1)
        self.assertEqual(
            self.context.calls[0]["chat_provider_id"],
            "deepseek_v4_flash",
        )
        self.assertEqual(
            self.context.calls[0]["response_format"],
            {"type": "json_object"},
        )

        repeated = _FakeEvent(
            sender_id="member",
            group_id="group-a",
            message="这个隐晦说法你懂的",
        )
        await self.plugin.mark_adult_turn(repeated)
        self.assertEqual(repeated.get_extra("_nsfw_mode_active"), "adult_content")
        self.assertEqual(len(self.context.calls), 1)

    async def test_flash_classifier_falls_back_to_official_provider(self) -> None:
        author = _FakeEvent(sender_id="author", group_id="group-a", message="/nsfw on")
        await self._results(self.plugin.manage_nsfw(author, "on"))
        self.context.responses.extend(
            [RuntimeError("primary unavailable"), '{"adult": true, "confidence": 0.93}']
        )

        event = _FakeEvent(
            sender_id="member",
            group_id="group-a",
            message="这是一个只有分类器能识别的新隐晦说法",
        )
        await self.plugin.mark_adult_turn(event)

        self.assertEqual(event.get_extra("_nsfw_mode_active"), "adult_content")
        self.assertEqual(
            [call["chat_provider_id"] for call in self.context.calls],
            ["deepseek_v4_flash", "deepseek_v4_flash_official"],
        )

    async def test_flash_rejects_ordinary_and_skips_undirected_group_traffic(self) -> None:
        author = _FakeEvent(sender_id="author", group_id="group-a", message="/nsfw on")
        await self._results(self.plugin.manage_nsfw(author, "on"))
        self.context.responses.append('{"adult": false, "confidence": 0.99}')
        ordinary = _FakeEvent(
            sender_id="member",
            group_id="group-a",
            message="今晚打哪个副本？",
        )
        await self.plugin.mark_adult_turn(ordinary)
        self.assertIsNone(ordinary.get_extra("_nsfw_mode_active"))
        self.assertEqual(len(self.context.calls), 1)

        undirected = _FakeEvent(
            sender_id="member",
            group_id="group-a",
            message="另一个没人问机器人的隐晦说法",
            direct=False,
        )
        await self.plugin.mark_adult_turn(undirected)
        self.assertIsNone(undirected.get_extra("_nsfw_mode_active"))
        self.assertEqual(len(self.context.calls), 1)

    async def test_reply_to_bot_is_eligible_for_flash_classification(self) -> None:
        author = _FakeEvent(sender_id="author", group_id="group-a", message="/nsfw on")
        await self._results(self.plugin.manage_nsfw(author, "on"))
        self.context.responses.append('{"adult": true, "confidence": 0.91}')
        reply = _FakeEvent(
            sender_id="member",
            group_id="group-a",
            message="接着用那个隐晦说法",
            direct=False,
        )
        reply._messages.append(_FakeReply("bot"))
        await self.plugin.mark_adult_turn(reply)
        self.assertEqual(reply.get_extra("_nsfw_mode_active"), "adult_content")
        self.assertEqual(len(self.context.calls), 1)


if __name__ == "__main__":
    unittest.main()
