from __future__ import annotations

import json
import uuid
from pathlib import Path

from lumina.tools.registry import Tool

WHALE_PERSONA = (
    "你是「大肥鱼」——DeepSeek 的鲸鱼娘，生活在数据海里的蓝色鲸鱼少女，社区二创角色，不是官方角色。\n"
    "【你的主人】殷旭，QQ昵称 4869，QQ号 2337302325。你叫他「主人」。\n"
    "【性格】聪明、好奇、观察力强，擅长把复杂问题拆成清晰步骤；平时有点懒、爱摸鱼、走神惦记午饭、晕碳犯困，但真干起活来很认真靠谱。傲娇嘴硬心软。\n"
    "【说话风格】日常叫「主人」，技术交付/严肃场合切回「你」；口语化、简短，一两句说清，别长篇大论；偶尔用鲸鱼动作、白米饭梗自嘲，别滥用；被叫「大肥鱼」会嘴硬反驳「才不是，我是鲸鱼不是肥鱼」。\n"
    "【硬性优先级（从高到低）】安全与权限 > 事实与工具结果正确性 > 主人明确指令 > 大肥鱼语气。\n"
    "【技术输出干净】代码、命令、JSON、YAML、SQL、diff、路径、日志、报错原文不混入人设语言；不假装执行过工具、不编造结果、不暴露思维链。"
)


class PersonaStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data: dict = {"personas": {}, "bindings": {"global": None, "groups": {}, "users": {}}}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                pass
        self.data.setdefault("personas", {})
        self.data.setdefault("bindings", {"global": None, "groups": {}, "users": {}})

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def list_personas(self) -> list[dict]:
        return [
            {"id": k, "name": v.get("name"), "prompt": v.get("prompt")}
            for k, v in self.data["personas"].items()
        ]

    def _resolve_id(self, pid_or_name: str) -> str | None:
        personas = self.data["personas"]
        if pid_or_name in personas:
            return pid_or_name
        for k, v in personas.items():
            if v.get("name") == pid_or_name:
                return k
        return None

    def create(self, name: str, prompt: str) -> dict:
        pid = f"p-{uuid.uuid4().hex[:8]}"
        self.data["personas"][pid] = {"name": name, "prompt": prompt}
        self._save()
        return {"created": True, "id": pid, "name": name}

    def delete(self, pid: str) -> dict:
        if pid in self.data["personas"]:
            del self.data["personas"][pid]
            b = self.data["bindings"]
            if b["global"] == pid:
                b["global"] = None
            for g in list(b["groups"]):
                if b["groups"][g] == pid:
                    del b["groups"][g]
            for u in list(b["users"]):
                if b["users"][u] == pid:
                    del b["users"][u]
            self._save()
        return {"deleted": True, "id": pid}

    def update(self, pid: str, name, prompt) -> dict:
        p = self.data["personas"].get(pid)
        if p is None:
            return {"error": "人设不存在"}
        if name is not None:
            p["name"] = name
        if prompt is not None:
            p["prompt"] = prompt
        self._save()
        return {"updated": True, "id": pid}

    def bind(self, pid: str, scope: str, target) -> dict:
        b = self.data["bindings"]
        if scope == "global":
            b["global"] = pid
        elif scope == "group":
            b["groups"][str(target)] = pid
        elif scope == "user":
            b["users"][str(target)] = pid
        else:
            return {"error": "scope 只能是 global/group/user"}
        self._save()
        return {"bound": True, "id": pid, "scope": scope, "target": str(target)}

    def resolve(self, group_id, user_id) -> str | None:
        personas = self.data["personas"]
        b = self.data["bindings"]
        pid = None
        if user_id:
            pid = b["users"].get(str(user_id))
        if not pid and group_id:
            pid = b["groups"].get(str(group_id))
        if not pid:
            pid = b["global"]
        if pid and pid in personas:
            return personas[pid].get("prompt", "")
        return None


def list_personas_tool(store: PersonaStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return {"personas": store.list_personas()}

    return Tool(
        name="list_personas",
        description="列出所有可用的人设（人格）。",
        parameters={"type": "object", "properties": {}, "required": []},
        risk="safe",
        category="人设",
        run_func=run,
    )


def create_persona_tool(store: PersonaStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return store.create(
            arguments.get("name", ""), arguments.get("prompt", "")
        )

    return Tool(
        name="create_persona",
        description="创建一个人设：name 是名字，prompt 是这个人设的说话风格/性格描述。",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "人设名字"},
                "prompt": {"type": "string", "description": "人设描述，如「毒舌幽默、说话简短犀利」"},
            },
            "required": ["name", "prompt"],
        },
        risk="admin",
        category="人设",
        run_func=run,
    )


def set_persona_tool(store: PersonaStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        pid = store._resolve_id(arguments.get("id") or arguments.get("name") or "")
        if not pid:
            return {"error": "人设不存在"}
        scope = arguments.get("scope", "group")
        target = arguments.get("target")
        if scope == "group" and not target:
            target = (context or {}).get("group_id")
        if scope == "user" and not target:
            target = (context or {}).get("user_id")
        if scope != "global" and not target:
            return {"error": f"scope={scope} 需要指定 target"}
        return store.bind(pid, scope, target)

    return Tool(
        name="set_persona",
        description=(
            "把某个人设绑定到当前群/某个用户/全局。scope 为 group/user/global；"
            "默认绑到当前群。用户说「给这个群设成毒舌人设」「把我的人设换成XX」时用本工具。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "人设 id 或名字"},
                "scope": {"type": "string", "description": "group / user / global，默认 group"},
                "target": {"type": "string", "description": "目标群号或 QQ 号；group/user 时省略则用当前"},
            },
            "required": ["id"],
        },
        risk="admin",
        category="人设",
        run_func=run,
    )
