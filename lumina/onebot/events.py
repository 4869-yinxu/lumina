from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MessageEvent:
    message_type: str  # "group" | "private"
    user_id: int
    group_id: int | None
    message: list[dict]
    raw_message: str
    message_id: int
    sender_nickname: str = ""


def parse_event(payload: dict) -> MessageEvent | None:
    if payload.get("post_type") != "message":
        return None
    if payload.get("message_type") not in ("group", "private"):
        return None
    sender = payload.get("sender") or {}
    nickname = sender.get("nickname") or sender.get("card") or ""
    return MessageEvent(
        message_type=payload["message_type"],
        user_id=int(payload["user_id"]),
        group_id=int(payload["group_id"]) if payload.get("group_id") else None,
        message=payload.get("message", []),
        raw_message=payload.get("raw_message", ""),
        message_id=int(payload["message_id"]),
        sender_nickname=nickname,
    )


def is_mentioned(event: MessageEvent, bot_id: int) -> bool:
    for seg in event.message:
        if seg.get("type") == "at" and str(seg.get("data", {}).get("qq", "")) == str(bot_id):
            return True
    return f"[CQ:at,qq={bot_id}]" in event.raw_message
