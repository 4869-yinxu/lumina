from __future__ import annotations

import contextlib
import json
import os
import re
from typing import Any

import yaml

from lumina.tools.registry import Tool

_ENV_RE = re.compile(r"^\$\{([A-Za-z0-9_]+)\}$")


def _resolve(value: Any, env: dict) -> Any:
    if isinstance(value, str):
        m = _ENV_RE.match(value.strip())
        if m:
            return env.get(m.group(1), "")
    return value


class McpClient:
    def __init__(self, name: str, command: str, args: list[str], env: dict):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.session = None
        self._stack: contextlib.AsyncExitStack | None = None

    async def start(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        full_env = {**os.environ, **self.env}
        params = StdioServerParameters(
            command=self.command, args=self.args, env=full_env
        )
        self._stack = contextlib.AsyncExitStack()
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(
            ClientSession(read, write)
        )
        await self.session.initialize()

    async def close(self) -> None:
        if self._stack:
            await self._stack.aclose()

    async def list_tools(self):
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, name: str, arguments: dict) -> Any:
        result = await self.session.call_tool(name, arguments)
        parts = []
        for c in result.content or []:
            t = getattr(c, "text", None)
            if t:
                parts.append(t)
        text = "".join(parts)
        try:
            return json.loads(text)
        except Exception:  # noqa: BLE001
            return {"result": text}


def load_mcp_config(path: str) -> list[dict]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:  # noqa: BLE001
        return []
    servers = cfg.get("servers", []) or []
    resolved = []
    for s in servers:
        s = dict(s)
        env = {}
        for k, v in (s.get("env") or {}).items():
            env[k] = _resolve(v, os.environ)
        s["env"] = env
        resolved.append(s)
    return resolved


def mcp_tool_to_agent_tool(client: McpClient, t, risk: str = "safe") -> Tool:
    schema = t.input_schema or {}
    parameters = {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }
    name = f"mcp_{client.name}_{t.name}"

    async def run(arguments: dict, context: dict | None = None) -> dict:
        return await client.call_tool(t.name, arguments)

    return Tool(
        name=name,
        description=f"[MCP:{client.name}] {t.description or ''}",
        parameters=parameters,
        risk=risk,
        category=f"MCP:{client.name}",
        run_func=run,
    )
