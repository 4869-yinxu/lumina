from __future__ import annotations

import json
import uuid
from pathlib import Path

from lumina.tools.registry import Tool


class SkillStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data: dict = {"skills": {}}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                pass
        self.data.setdefault("skills", {})

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def list_skills(self) -> list[dict]:
        return [
            {"id": k, **v} for k, v in self.data["skills"].items()
        ]

    def create(self, name: str, trigger: str, prompt: str) -> dict:
        sid = f"s-{uuid.uuid4().hex[:8]}"
        triggers = [t.strip() for t in (trigger or "").split(",") if t.strip()]
        self.data["skills"][sid] = {
            "name": name, "trigger": triggers, "prompt": prompt,
        }
        self._save()
        return {"created": True, "id": sid, "name": name}

    def delete(self, sid: str) -> dict:
        if sid in self.data["skills"]:
            del self.data["skills"][sid]
            self._save()
        return {"deleted": True, "id": sid}

    def match(self, message: str) -> list[dict]:
        """返回匹配的技能的 prompt 列表（按触发词命中）。"""
        out = []
        msg = (message or "").lower()
        for k, v in self.data["skills"].items():
            for t in v.get("trigger", []):
                if t and t.lower() in msg:
                    out.append(v)
                    break
        return out


def list_skills_tool(store: SkillStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return {"skills": store.list_skills()}

    return Tool(
        name="list_skills",
        description="列出所有已定义的技能。",
        parameters={"type": "object", "properties": {}, "required": []},
        risk="safe",
        category="技能",
        run_func=run,
    )


def create_skill_tool(store: SkillStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return store.create(
            arguments.get("name", ""),
            arguments.get("trigger", ""),
            arguments.get("prompt", ""),
        )

    return Tool(
        name="create_skill",
        description=(
            "创建一个技能：name 是技能名；trigger 是触发词（逗号分隔，命中就自动应用）；"
            "prompt 是技能要执行的指令/步骤。例如「查天气」技能：trigger='天气'，prompt='用 web_search 查当地天气并给出穿衣建议'。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名"},
                "trigger": {"type": "string", "description": "触发词，逗号分隔"},
                "prompt": {"type": "string", "description": "技能指令/步骤"},
            },
            "required": ["name", "prompt"],
        },
        risk="admin",
        category="技能",
        run_func=run,
    )


def delete_skill_tool(store: SkillStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return store.delete(arguments.get("id", ""))

    return Tool(
        name="delete_skill",
        description="删除一个技能。",
        parameters={
            "type": "object",
            "properties": {"id": {"type": "string", "description": "技能 id"}},
            "required": ["id"],
        },
        risk="admin",
        category="技能",
        run_func=run,
    )
