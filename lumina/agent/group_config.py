from __future__ import annotations

import json
from pathlib import Path

from lumina.tools.registry import Tool

DEFAULT_REPLY_MODE = "mention_only"


class GroupConfig:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data: dict = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                self.data = {}

    def reply_mode(self, group_id) -> str:
        return str(
            self.data.get(str(group_id), {}).get("reply_mode", DEFAULT_REPLY_MODE)
        )

    def set_reply_mode(self, group_id, mode: str) -> dict:
        self.data.setdefault(str(group_id), {})["reply_mode"] = mode
        self._save()
        return {"ok": True, "group_id": group_id, "reply_mode": mode}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def set_group_config_tool(config: GroupConfig) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        gid = (context or {}).get("group_id")
        if not gid:
            return {"error": "只能在群里设置"}
        mode = arguments.get("reply_mode")
        if mode in ("mention_only", "all"):
            return config.set_reply_mode(gid, mode)
        return {"error": "reply_mode 只能是 mention_only 或 all"}

    return Tool(
        name="set_group_config",
        description=(
            "修改本群的行为配置。reply_mode='mention_only' 表示群里只有@机器人才回复；"
            "reply_mode='all' 表示群里所有消息都回复。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "reply_mode": {"type": "string", "description": "mention_only 或 all"},
            },
            "required": ["reply_mode"],
        },
        risk="admin",
        category="管理",
        run_func=run,
    )
