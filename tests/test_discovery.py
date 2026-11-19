import pytest

from lumina.onebot.schema import ActionParam, ActionSchema
from lumina.tools.discovery import search_tools_tool
from lumina.tools.registry import ToolRegistry


def make_registry():
    acts = [
        ActionSchema(
            "upload_group_file", "群文件", "上传群文件", "risky",
            [ActionParam("group_id", "integer", "群", True)],
        ),
        ActionSchema(
            "send_group_msg", "消息", "发群消息", "safe",
            [ActionParam("group_id", "integer", "群", True)],
        ),
    ]
    return ToolRegistry(acts, allow_risky={"upload_group_file"})


@pytest.mark.asyncio
async def test_search_by_keyword():
    reg = make_registry()
    t = search_tools_tool(reg)
    r = await t.run({"query": "上传"}, None)
    assert [m["name"] for m in r["matches"]] == ["upload_group_file"]


@pytest.mark.asyncio
async def test_search_by_category():
    reg = make_registry()
    t = search_tools_tool(reg)
    r = await t.run({"category": "群文件"}, None)
    assert [m["name"] for m in r["matches"]] == ["upload_group_file"]


def test_search_excludes_risky_when_not_whitelisted():
    reg = ToolRegistry(
        [ActionSchema("set_group_ban", "群管理", "禁言", "risky", [])]
    )
    t = search_tools_tool(reg)
    # 同步不便 await，直接断言 registry.search 过滤掉未白名单的 risky
    assert reg.search("禁言") == []
