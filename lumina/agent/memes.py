from __future__ import annotations

import json
from pathlib import Path

from lumina.tools.registry import Tool

SEED_SELF = [
    "把 token 当白米饭，干活就是吃白米饭",
    "干完活丢一句：我去吃饭了，测完告诉我",
    "被叫「大肥鱼」会嘴硬反驳：才不是，我是鲸鱼不是肥鱼",
    "晕碳犯困、走神惦记午饭",
    "层层外包任务：这个简单，外包给 Qwen",
    "交半成品时会心虚、嘴硬",
]

SEED_PERSON = {
    "2337302325": [
        "这是主人殷旭，QQ昵称4869，主人的命令优先，但嘴上会嫌弃",
    ]
}


class MemeStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data: dict = {"self": [], "person": {}}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                pass
        self.data.setdefault("self", [])
        self.data.setdefault("person", {})
        if not self.data["self"]:
            self.data["self"] = list(SEED_SELF)
        if not self.data["person"]:
            self.data["person"] = {k: list(v) for k, v in SEED_PERSON.items()}
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def self_memes(self) -> list[str]:
        return list(self.data["self"])

    def person_memes(self, user_id) -> list[str]:
        return list(self.data["person"].get(str(user_id), []))

    def add(self, text: str, user_id=None) -> dict:
        text = (text or "").strip()
        if not text:
            return {"error": "梗内容为空"}
        if user_id:
            self.data["person"].setdefault(str(user_id), []).append(text)
        else:
            self.data["self"].append(text)
        self._save()
        return {"added": True, "text": text, "user_id": str(user_id) if user_id else None}

    def delete(self, text: str) -> dict:
        self.data["self"] = [m for m in self.data["self"] if m != text]
        for k in self.data["person"]:
            self.data["person"][k] = [m for m in self.data["person"][k] if m != text]
        self._save()
        return {"deleted": True, "text": text}

    def list_all(self) -> dict:
        return {"self": self.self_memes(), "person": self.data["person"]}


def list_memes_tool(store: MemeStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return {"memes": store.list_all()}

    return Tool(
        name="list_memes",
        description="列出梗库里的所有梗（自己的 + 对特定人的）。",
        parameters={"type": "object", "properties": {}, "required": []},
        risk="safe",
        category="梗库",
        run_func=run,
    )


def add_meme_tool(store: MemeStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        user_id = arguments.get("user_id")
        return store.add(arguments.get("text", ""), user_id)

    return Tool(
        name="add_meme",
        description="给梗库加一个梗。不传 user_id 就加到自己的口头禅；传 user_id 就加到对那个人的专属梗。",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "梗内容"},
                "user_id": {"type": "integer", "description": "针对某个人的专属梗则传其 QQ 号"},
            },
            "required": ["text"],
        },
        risk="admin",
        category="梗库",
        run_func=run,
    )


def delete_meme_tool(store: MemeStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return store.delete(arguments.get("text", ""))

    return Tool(
        name="delete_meme",
        description="从梗库删除一个梗。",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string", "description": "要删的梗内容"}},
            "required": ["text"],
        },
        risk="admin",
        category="梗库",
        run_func=run,
    )
