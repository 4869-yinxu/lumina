from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from lumina.onebot.schema import ActionSchema

_LEVEL_RANK = {"user": 0, "vip": 1, "svip": 2, "developer": 3}


def action_parameters(action: ActionSchema) -> dict:
    properties = {
        p.name: {"type": p.type, "description": p.description} for p in action.params
    }
    required = [p.name for p in action.params if p.required]
    return {"type": "object", "properties": properties, "required": required}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    risk: str = "safe"  # safe / risky / admin（forbidden 不加载）
    category: str = ""
    run_func: Callable[[dict, dict], Awaitable[dict]] | None = None
    action_name: str | None = None

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def run(self, arguments: dict, client, context: dict | None = None) -> dict:
        if self.run_func is not None:
            return await self.run_func(arguments, context or {})
        return await client.call_action(self.action_name or self.name, arguments)


def action_to_tool(action: ActionSchema) -> Tool:
    return Tool(
        name=action.name,
        description=action.description,
        parameters=action_parameters(action),
        risk=action.risk,
        category=action.category,
        action_name=action.name,
    )


class ToolRegistry:
    def __init__(self, actions: list[ActionSchema], allow_risky: set[str] | None = None):
        self._by_name: dict[str, Tool] = {}
        self._allow_risky = allow_risky or set()
        for a in actions:
            if a.risk == "forbidden":
                continue
            self._by_name[a.name] = action_to_tool(a)

    def add(self, tool: Tool) -> None:
        self._by_name[tool.name] = tool

    def set_allow_risky(self, names: set[str]) -> None:
        self._allow_risky = set(names)

    def get_allow_risky(self) -> set[str]:
        return set(self._allow_risky)

    def _enabled(self, tool: Tool, level: str = "developer") -> bool:
        rank = _LEVEL_RANK.get(level, 0)
        if tool.risk == "safe":
            return True
        if tool.risk == "risky":
            return rank >= _LEVEL_RANK["vip"] and tool.name in self._allow_risky
        if tool.risk == "admin":
            return rank >= _LEVEL_RANK["svip"]
        return False

    def all_tools(self) -> list[Tool]:
        return list(self._by_name.values())

    def openai_tools(self, level: str = "developer") -> list[dict]:
        return [t.to_openai() for t in self._by_name.values() if self._enabled(t, level)]

    def openai_tools_for(self, names: set[str], level: str = "developer") -> list[dict]:
        return [
            t.to_openai()
            for t in self._by_name.values()
            if t.name in names and self._enabled(t, level)
        ]

    def search(self, query: str = "", category: str = "", level: str = "developer") -> list[Tool]:
        q = (query or "").strip().lower()
        cat = (category or "").strip()
        out = []
        for t in self._by_name.values():
            if not self._enabled(t, level):
                continue
            if cat and t.category != cat:
                continue
            if q and q not in t.name.lower() and q not in t.description.lower():
                continue
            out.append(t)
        return out

    def get(self, name: str, level: str = "developer") -> Tool | None:
        tool = self._by_name.get(name)
        if tool is None or not self._enabled(tool, level):
            return None
        return tool
