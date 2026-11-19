import asyncio
import json

import httpx
import pytest
import websockets

from lumina.onebot.client import OneBotClient
from lumina.onebot.events import MessageEvent, is_mentioned, parse_event


@pytest.mark.asyncio
async def test_call_action_http_sends_bearer_and_returns_data():
    async def handler(request: httpx.Request):
        assert request.url.path == "/get_group_list"
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json={"status": "ok", "data": {"groups": []}})

    c = OneBotClient(
        http_url="http://snowluma:3000/",
        ws_url="ws://snowluma:3001/",
        http_token="tok",
    )
    c._http = httpx.AsyncClient(base_url=c.http_url, transport=httpx.MockTransport(handler))
    data = await c.call_action("get_group_list", {})
    assert data == {"groups": []}
    await c.aclose()


@pytest.mark.asyncio
async def test_call_action_http_raises_on_failure():
    async def handler(request: httpx.Request):
        return httpx.Response(200, json={"status": "failed", "retcode": 1})

    c = OneBotClient(http_url="http://snowluma:3000/", ws_url="ws://snowluma:3001/")
    c._http = httpx.AsyncClient(base_url=c.http_url, transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError):
        await c.call_action("get_group_list", {})
    await c.aclose()


def test_parse_group_message():
    e = parse_event(
        {
            "post_type": "message",
            "message_type": "group",
            "user_id": 123,
            "group_id": 456,
            "message": [{"type": "text", "data": {"text": "hi"}}],
            "raw_message": "hi",
            "message_id": 789,
            "sender": {"user_id": 123, "nickname": "小明", "card": "小明"},
        }
    )
    assert isinstance(e, MessageEvent)
    assert e.group_id == 456
    assert e.raw_message == "hi"
    assert e.sender_nickname == "小明"


def test_parse_sender_missing_falls_back_to_empty():
    e = parse_event(
        {
            "post_type": "message",
            "message_type": "group",
            "user_id": 123,
            "group_id": 456,
            "message": [],
            "raw_message": "hi",
            "message_id": 789,
        }
    )
    assert e.sender_nickname == ""


def test_parse_ignores_non_message():
    assert parse_event({"post_type": "notice"}) is None
    assert parse_event({"post_type": "message", "message_type": "guild"}) is None


def test_is_mentioned_array_segment():
    e = MessageEvent(
        "group", 1, 2,
        [{"type": "at", "data": {"qq": "3837425549"}}, {"type": "text", "data": {"text": "hi"}}],
        "", 1,
    )
    assert is_mentioned(e, 3837425549) is True


def test_is_mentioned_false():
    e = MessageEvent("group", 1, 2, [{"type": "text", "data": {"text": "hi"}}], "hi", 1)
    assert is_mentioned(e, 3837425549) is False


def test_is_mentioned_cq_string_fallback():
    e = MessageEvent("group", 1, 2, [], "[CQ:at,qq=3837425549] hi", 1)
    assert is_mentioned(e, 3837425549) is True


@pytest.mark.asyncio
async def test_reverse_ws_event_delivery():
    c = OneBotClient(
        http_url="http://x/", ws_url="ws://x/", reverse_host="127.0.0.1", reverse_port=18090
    )
    received = []

    async def on_event(e):
        received.append(e)

    server = asyncio.create_task(c.serve_ws(on_event))
    try:
        await asyncio.sleep(0.3)
        async with websockets.connect("ws://127.0.0.1:18090/ws") as ws:
            await ws.send(
                json.dumps(
                    {
                        "post_type": "message",
                        "message_type": "group",
                        "user_id": 1,
                        "group_id": 2,
                        "message": [],
                        "raw_message": "hi",
                        "message_id": 3,
                    }
                )
            )
            await asyncio.sleep(0.3)
        assert len(received) == 1
        assert received[0]["raw_message"] == "hi"
    finally:
        server.cancel()
