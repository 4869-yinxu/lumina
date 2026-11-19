import pytest

from lumina.agent.websearch import search, web_search_tool


def test_web_search_tool_shape():
    t = web_search_tool()
    d = t.to_openai()
    assert d["function"]["name"] == "web_search"
    assert "query" in d["function"]["parameters"]["required"]


@pytest.mark.asyncio
async def test_search_empty_query():
    r = await search({"query": ""})
    assert "error" in r
