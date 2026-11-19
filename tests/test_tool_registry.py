from pathlib import Path

from lumina.onebot.schema import load_actions
from lumina.tools.registry import ToolRegistry

ACTIONS = load_actions(
    Path(__file__).parent.parent / "lumina" / "tools" / "snowluma_actions.json"
)


def test_forbidden_not_loaded():
    reg = ToolRegistry(ACTIONS)
    assert reg.get("bot_exit") is None
    assert reg.get("get_credentials") is None


def test_risky_disabled_by_default():
    reg = ToolRegistry(ACTIONS)
    assert reg.get("set_group_ban") is None
    names = [t["function"]["name"] for t in reg.openai_tools()]
    assert "set_group_ban" not in names
    assert "send_group_msg" in names


def test_risky_enabled_when_whitelisted():
    reg = ToolRegistry(ACTIONS, allow_risky={"set_group_ban"})
    assert reg.get("set_group_ban") is not None
    assert "set_group_ban" in [t["function"]["name"] for t in reg.openai_tools()]


def test_openai_tool_shape():
    tool = ToolRegistry(ACTIONS).get("send_group_msg")
    d = tool.to_openai()
    assert d["type"] == "function"
    assert d["function"]["parameters"]["required"] == ["group_id", "message"]
