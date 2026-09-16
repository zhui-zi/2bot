from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qq_reply import bind_group_reference  # noqa: E402


class GroupReferenceTests(unittest.IsolatedAsyncioTestCase):
    def event(self):
        async def send(send_func, payload, plain_text, stream=None):
            return await send_func(payload)

        return SimpleNamespace(_send_with_markdown_fallback=send)

    async def send(self, event, payload):
        async def capture(body):
            await asyncio.sleep(0)
            return body

        return await event._send_with_markdown_fallback(
            send_func=capture,
            payload=payload,
            plain_text="完整回复",
        )

    async def test_native_reference_uses_plain_text_without_mutating_payload(self):
        event = self.event()
        self.assertTrue(bind_group_reference(event, "message-a"))
        payload = {
            "msg_type": 2,
            "markdown": {"content": "完整回复"},
            "msg_id": "message-a",
        }
        result = await self.send(event, payload)
        self.assertEqual(result["message_reference"]["message_id"], "message-a")
        self.assertTrue(result["message_reference"]["ignore_get_message_error"])
        self.assertEqual(result["content"], "完整回复")
        self.assertEqual(result["msg_type"], 0)
        self.assertNotIn("markdown", result)
        self.assertIn("markdown", payload)

    async def test_concurrent_events_keep_their_own_references(self):
        first, second = self.event(), self.event()
        bind_group_reference(first, "message-a")
        bind_group_reference(second, "message-b")
        results = await asyncio.gather(self.send(first, {}), self.send(second, {}))
        self.assertEqual(
            [r["message_reference"]["message_id"] for r in results],
            ["message-a", "message-b"],
        )

    async def test_media_payload_is_preserved(self):
        event = self.event()
        bind_group_reference(event, "message-a")
        result = await self.send(
            event, {"msg_type": 7, "media": {"file_info": "image"}, "content": "图片"}
        )
        self.assertEqual(result["msg_type"], 7)
        self.assertEqual(result["media"], {"file_info": "image"})
        self.assertEqual(result["content"], "图片")

    async def test_existing_reference_is_replaced_by_triggering_message(self):
        event = self.event()
        bind_group_reference(event, "message-a")
        result = await self.send(event, {"message_reference": {"message_id": "wrong"}})
        self.assertEqual(result["message_reference"]["message_id"], "message-a")

    async def test_repeated_binding_does_not_stack_wrappers(self):
        event = self.event()
        bind_group_reference(event, "message-a")
        wrapper = event._send_with_markdown_fallback
        bind_group_reference(event, "message-a")
        self.assertIs(wrapper, event._send_with_markdown_fallback)

    async def test_send_failure_is_not_swallowed(self):
        event = self.event()
        bind_group_reference(event, "message-a")

        async def reject(_payload):
            raise RuntimeError("send failed")

        with self.assertRaisesRegex(RuntimeError, "send failed"):
            await event._send_with_markdown_fallback(reject, {}, "完整回复")

    async def test_unsupported_adapter_is_detected(self):
        self.assertFalse(bind_group_reference(SimpleNamespace(), "message-a"))
