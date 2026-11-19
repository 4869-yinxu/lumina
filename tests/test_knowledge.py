import pytest

from lumina.agent.knowledge import KnowledgeBase, kb_add_tool, kb_query_tool


@pytest.mark.asyncio
async def test_add_query_list_delete(tmp_path):
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    await kb.add("user:1", "我喜欢吃火锅")
    await kb.add("user:1", "我的生日是 5 月 1 号")
    await kb.add("user:2", "别人的信息")

    docs = await kb.list_docs("user:1")
    assert len(docs) == 2

    hits = await kb.query("user:1", "生日")
    assert len(hits) == 1
    assert "生日" in hits[0]["text"]

    await kb.delete("user:1", docs[0]["id"])
    assert len(await kb.list_docs("user:1")) == 1


@pytest.mark.asyncio
async def test_kb_tools_scope_by_user(tmp_path):
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    add = kb_add_tool(kb)
    query = kb_query_tool(kb)
    await add.run({"text": "我养了一只猫"}, None, {"user_id": 111})
    r = await query.run({"query": "猫"}, None, {"user_id": 222})
    assert r["results"] == []
    r = await query.run({"query": "猫"}, None, {"user_id": 111})
    assert len(r["results"]) == 1
