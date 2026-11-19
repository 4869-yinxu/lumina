import pytest

from lumina.agent.loop import Agent
from lumina.config import Settings
from lumina.llm.base import ChatMessage, ChatResponse, LLMProvider, ToolCall
from lumina.memory.store import MemoryStore
from lumina.onebot.events import MessageEvent
from lumina.onebot.schema import ActionSchema, ActionParam
from lumina.tools.registry import ToolRegistry


class FakeProvider(LLMProvider):
    def __init__(self, replies):
        self.replies = list(replies)
        self.messages = None

    async def complete(self, messages, tools, max_tokens=2048):
        self.messages = messages
        return self.replies.pop(0)


class FakeClient:
    def __init__(self, results=None):
        self.results = results or {}
        self.calls = []

    async def call_action(self, action, params):
        self.calls.append((action, params))
        r = self.results.get(action)
        if callable(r):
            return r(params)
        return r if r is not None else {}


def make_settings(tmp_path):
    return Settings(deepseek_api_key="k", db_path=str(tmp_path / "m.db"), _env_file=None)


@pytest.mark.asyncio
async def test_single_tool_call_flow(tmp_path):
    act = ActionSchema(
        "get_group_member_info",
        "群信息",
        "查成员",
        "safe",
        [
            ActionParam("group_id", "integer", "群", True),
            ActionParam("user_id", "integer", "人", True),
        ],
    )
    reg = ToolRegistry([act])
    provider = FakeProvider(
        [
            ChatResponse(
                ChatMessage(
                    "assistant",
                    "",
                    [ToolCall("c1", "get_group_member_info", {"group_id": 1, "user_id": 2})],
                ),
                "tool_calls",
            ),
            ChatResponse(ChatMessage("assistant", "成员叫小明"), "stop"),
        ]
    )
    client = FakeClient(
        {
            "get_group_info": {"group_name": "夜包子"},
            "get_group_member_info": {"nickname": "小明"},
        }
    )
    agent = Agent(provider, reg, client, MemoryStore(make_settings(tmp_path).db_path), make_settings(tmp_path))
    out = await agent.handle_message(
        MessageEvent("group", 2, 1, [], "查一下这个人", 1, sender_nickname="foodd")
    )
    assert out == "成员叫小明"
    assert ("get_group_member_info", {"group_id": 1, "user_id": 2}) in client.calls


@pytest.mark.asyncio
async def test_no_tool_reply(tmp_path):
    reg = ToolRegistry([])
    provider = FakeProvider([ChatResponse(ChatMessage("assistant", "你好"), "stop")])
    client = FakeClient({})
    agent = Agent(provider, reg, client, MemoryStore(make_settings(tmp_path).db_path), make_settings(tmp_path))
    out = await agent.handle_message(MessageEvent("private", 2, None, [], "你好", 1))
    assert out == "你好"


@pytest.mark.asyncio
async def test_group_message_labeled_with_sender(tmp_path):
    reg = ToolRegistry([])
    provider = FakeProvider([ChatResponse(ChatMessage("assistant", "ok"), "stop")])
    client = FakeClient({"get_group_info": {"group_name": "夜包子"}})
    settings = make_settings(tmp_path)
    memory = MemoryStore(settings.db_path)
    agent = Agent(provider, reg, client, memory, settings)
    await agent.handle_message(
        MessageEvent("group", 3023996221, 1078607099, [], "你是谁", 1, sender_nickname="foodd")
    )
    recent = await memory.recent("group:1078607099")
    assert recent[0].content == "[foodd] 你是谁"


@pytest.mark.asyncio
async def test_group_message_falls_back_to_user_id(tmp_path):
    reg = ToolRegistry([])
    provider = FakeProvider([ChatResponse(ChatMessage("assistant", "ok"), "stop")])
    client = FakeClient({"get_group_info": {"group_name": "夜包子"}})
    settings = make_settings(tmp_path)
    memory = MemoryStore(settings.db_path)
    agent = Agent(provider, reg, client, memory, settings)
    await agent.handle_message(MessageEvent("group", 3023996221, 1078607099, [], "你好", 1))
    recent = await memory.recent("group:1078607099")
    assert recent[0].content == "[3023996221] 你好"


@pytest.mark.asyncio
async def test_context_includes_group_name_and_sender(tmp_path):
    reg = ToolRegistry([])
    provider = FakeProvider([ChatResponse(ChatMessage("assistant", "ok"), "stop")])
    client = FakeClient({"get_group_info": {"group_name": "夜包子"}})
    settings = make_settings(tmp_path)
    agent = Agent(provider, reg, client, MemoryStore(settings.db_path), settings)
    await agent.handle_message(
        MessageEvent("group", 3023996221, 1078607099, [], "你好", 1, sender_nickname="foodd")
    )
    system = provider.messages[0].content
    assert "夜包子" in system
    assert "foodd" in system
    assert "1078607099" in system
    assert "当前时间" in system
