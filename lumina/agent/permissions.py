from __future__ import annotations

import json
from pathlib import Path

from lumina.tools.registry import Tool

# 级别数值：越高权限越大
LEVELS = {"user": 0, "vip": 1, "svip": 2, "developer": 3}


class PermissionStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data: dict = {"developer": [], "svip": [], "vip": []}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                pass
        for k in ("developer", "svip", "vip"):
            self.data.setdefault(k, [])

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_level(self, user_id) -> str:
        uid = str(user_id)
        for level in ("developer", "svip", "vip"):
            if uid in [str(u) for u in self.data.get(level, [])]:
                return level
        return "user"

    def grant(self, user_id, level: str) -> dict:
        if level not in LEVELS or level == "user":
            return {"error": "level 只能是 developer/svip/vip"}
        uid = str(user_id)
        for lv in ("developer", "svip", "vip"):
            self.data[lv] = [u for u in self.data[lv] if str(u) != uid]
        self.data[level].append(uid)
        self._save()
        return {"granted": True, "user_id": uid, "level": level}

    def revoke(self, user_id) -> dict:
        uid = str(user_id)
        for lv in ("developer", "svip", "vip"):
            self.data[lv] = [u for u in self.data[lv] if str(u) != uid]
        self._save()
        return {"revoked": True, "user_id": uid}

    def list_permissions(self) -> dict:
        return {k: list(v) for k, v in self.data.items()}


def list_permissions_tool(store: PermissionStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return {"permissions": store.list_permissions()}

    return Tool(
        name="list_permissions",
        description="列出各级别用户名单。",
        parameters={"type": "object", "properties": {}, "required": []},
        risk="admin",
        category="权限",
        run_func=run,
    )


def grant_permission_tool(store: PermissionStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        user_id = arguments.get("user_id")
        level = arguments.get("level", "")
        if not user_id:
            user_id = (context or {}).get("user_id")
        return store.grant(user_id, level)

    return Tool(
        name="grant_permission",
        description="授予/调整某用户的权限级别（developer/svip/vip）。仅最高权限者可用。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "要授权的 QQ 号"},
                "level": {"type": "string", "description": "developer / svip / vip"},
            },
            "required": ["level"],
        },
        risk="admin",
        category="权限",
        run_func=run,
    )


def revoke_permission_tool(store: PermissionStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        user_id = arguments.get("user_id")
        if not user_id:
            user_id = (context or {}).get("user_id")
        return store.revoke(user_id)

    return Tool(
        name="revoke_permission",
        description="取消某用户的权限（降回普通用户）。仅最高权限者可用。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "要取消权限的 QQ 号"},
            },
            "required": ["user_id"],
        },
        risk="admin",
        category="权限",
        run_func=run,
    )


def set_risky_permission_tool(registry, allowlist_path) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        names = arguments.get("names", []) or []
        enabled = arguments.get("enabled", True)
        current = registry.get_allow_risky()
        for n in names:
            if enabled:
                current.add(n)
            else:
                current.discard(n)
        registry.set_allow_risky(current)
        try:
            Path(allowlist_path).write_text(
                json.dumps(sorted(current)), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "allow_risky": sorted(current)}

    return Tool(
        name="set_risky_permission",
        description=(
            "开启或关闭某些 risky 工具的权限（加入/移出白名单）。"
            "names 是工具名列表；enabled=true 开启、false 关闭。仅最高权限者可用。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"}, "description": "工具名列表，如 ['set_group_name','set_qq_avatar']"},
                "enabled": {"type": "boolean", "description": "true 开启、false 关闭"},
            },
            "required": ["names"],
        },
        risk="admin",
        category="权限",
        run_func=run,
    )
