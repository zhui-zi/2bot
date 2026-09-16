from __future__ import annotations

from typing import Any


def bind_group_reference(event: Any, message_id: str) -> bool:
    """Attach a QQ reference to this event's send payload without shared patches."""
    send = getattr(event, "_send_with_markdown_fallback", None)
    if not callable(send):
        return False
    if getattr(event, "_mention_only_group_reference", None) == message_id:
        return True

    async def send_with_reference(send_func, payload, plain_text, stream=None):
        referenced = dict(payload)
        referenced["message_reference"] = {
            "message_id": message_id,
            "ignore_get_message_error": True,
        }
        # QQ clients render native references on plain group messages.
        if referenced.get("msg_type") == 2:
            referenced.pop("markdown", None)
            referenced["msg_type"] = 0
            referenced["content"] = plain_text
        return await send(
            send_func=send_func,
            payload=referenced,
            plain_text=plain_text,
            stream=stream,
        )

    event._send_with_markdown_fallback = send_with_reference
    event._mention_only_group_reference = message_id
    return True
