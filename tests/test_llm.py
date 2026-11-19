import json

from lumina.llm.base import ChatMessage, ToolCall
from lumina.llm.openai_compat import OpenAICompatProvider


def _provider():
    return OpenAICompatProvider(
        api_key="k", base_url="https://api.deepseek.com", model="deepseek-flash"
    )


def test_to_openai_assistant_with_tool_call():
    p = _provider()
    m = ChatMessage(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="c1", name="calc", arguments={"a": 1, "b": 2})],
    )
    out = p._to_openai(m)
    assert out["role"] == "assistant"
    assert out["tool_calls"][0]["function"]["name"] == "calc"
    assert out["tool_calls"][0]["function"]["arguments"] == json.dumps({"a": 1, "b": 2})


def test_to_openai_tool_message():
    p = _provider()
    out = p._to_openai(ChatMessage(role="tool", content="42", tool_call_id="c1"))
    assert out == {"role": "tool", "content": "42", "tool_call_id": "c1"}


def test_to_openai_plain_user_message():
    p = _provider()
    out = p._to_openai(ChatMessage(role="user", content="hi"))
    assert out == {"role": "user", "content": "hi"}
