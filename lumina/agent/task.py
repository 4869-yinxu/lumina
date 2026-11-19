from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiosqlite

from lumina.tools.registry import Tool

_client = None
_task_store = None


def _set_task_context(client, task_store):
    global _client, _task_store
    _client = client
    _task_store = task_store


async def _fire_task_deadline(task_id: str, creator_id: str):
    task = await _task_store.get(task_id)
    if not task or task["status"] != "pending":
        return
    results = await _task_store.get_results(task_id)
    replied = [r["user_id"] for r in results]
    participants = task["participants"]
    not_replied = [p for p in participants if p not in replied]
    summary = (
        f"任务「{task['description']}」已截止。\n"
        f"已回复 {len(replied)}/{len(participants)} 人：{', '.join(replied) or '无'}。\n"
        f"未回复：{', '.join(not_replied) or '无'}。"
    )
    await _client.call_action(
        "send_private_msg", {"user_id": int(creator_id), "message": summary}
    )
    await _task_store.complete(task_id)


class TaskStore:
    def __init__(self, db_path: str):
        self._db_path = db_path

    async def _conn(self):
        conn = await aiosqlite.connect(self._db_path)
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "id TEXT PRIMARY KEY, creator_id TEXT, description TEXT,"
            "participants TEXT, deadline REAL, status TEXT, created_at REAL)"
        )
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS task_results ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,"
            "user_id TEXT, reply TEXT, at REAL)"
        )
        await conn.commit()
        return conn

    async def create(self, creator_id, description, participants, deadline_seconds):
        tid = uuid.uuid4().hex[:12]
        conn = await self._conn()
        await conn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?)",
            (
                tid, str(creator_id), description,
                json.dumps([str(p) for p in participants]),
                time.time() + int(deadline_seconds), "pending", time.time(),
            ),
        )
        await conn.commit()
        await conn.close()
        return tid

    async def get(self, task_id: str) -> dict | None:
        conn = await self._conn()
        cur = await conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        row = await cur.fetchone()
        await conn.close()
        if not row:
            return None
        return {
            "id": row[0], "creator_id": row[1], "description": row[2],
            "participants": json.loads(row[3]), "deadline": row[4],
            "status": row[5], "created_at": row[6],
        }

    async def active_tasks(self, user_id) -> list[dict]:
        conn = await self._conn()
        cur = await conn.execute(
            "SELECT * FROM tasks WHERE status='pending' AND deadline > ?",
            (time.time(),),
        )
        rows = await cur.fetchall()
        await conn.close()
        out = []
        for r in rows:
            participants = json.loads(r[3])
            if str(user_id) in participants:
                out.append({
                    "id": r[0], "description": r[2], "deadline": r[4],
                })
        return out

    async def submit_result(self, task_id, user_id, reply) -> dict:
        conn = await self._conn()
        await conn.execute(
            "INSERT INTO task_results (task_id, user_id, reply, at) VALUES (?,?,?,?)",
            (task_id, str(user_id), reply, time.time()),
        )
        await conn.commit()
        await conn.close()
        return {"submitted": True, "task_id": task_id, "user_id": str(user_id)}

    async def get_results(self, task_id) -> list[dict]:
        conn = await self._conn()
        cur = await conn.execute(
            "SELECT user_id, reply FROM task_results WHERE task_id=?", (task_id,)
        )
        rows = await cur.fetchall()
        await conn.close()
        return [{"user_id": r[0], "reply": r[1]} for r in rows]

    async def complete(self, task_id) -> None:
        conn = await self._conn()
        await conn.execute("UPDATE tasks SET status='completed' WHERE id=?", (task_id,))
        await conn.commit()
        await conn.close()

    async def list_tasks(self) -> list[dict]:
        conn = await self._conn()
        cur = await conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50")
        rows = await cur.fetchall()
        await conn.close()
        return [
            {
                "id": r[0], "creator_id": r[1], "description": r[2],
                "participants": json.loads(r[3]), "deadline": r[4], "status": r[5],
            }
            for r in rows
        ]


def create_task_tool(store: TaskStore, scheduler) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        creator_id = (context or {}).get("user_id")
        description = arguments.get("description", "")
        participants = arguments.get("participants", []) or []
        deadline_seconds = int(arguments.get("deadline_seconds", 0))
        if not description or not participants:
            return {"error": "需要 description 和 participants"}
        tid = await store.create(creator_id, description, participants, deadline_seconds)
        for p in participants:
            try:
                await _client.call_action(
                    "send_private_msg",
                    {"user_id": int(p), "message": f"有个任务请你完成：{description}。完成后直接回复我即可。"},
                )
            except Exception:  # noqa: BLE001
                pass
        run_at = datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(seconds=deadline_seconds)
        scheduler.schedule_once(_fire_task_deadline, [tid, str(creator_id)], run_at)
        return {
            "created": True, "task_id": tid,
            "deadline": run_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

    return Tool(
        name="create_task",
        description=(
            "创建一个多参与者任务：私信通知 participants 里每个人完成 description，"
            "到截止时间（deadline_seconds 秒后）自动汇总谁回复了、谁没回复，反馈给发起人。"
            "用于「私信通知几个人完成某件事并汇总反馈」这类需求。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "任务内容，如「完成调查问卷」"},
                "participants": {"type": "array", "items": {"type": "integer"}, "description": "参与者的 QQ 号列表"},
                "deadline_seconds": {"type": "integer", "description": "多少秒后截止，如 2 小时=7200"},
            },
            "required": ["description", "participants", "deadline_seconds"],
        },
        risk="risky",
        category="任务",
        run_func=run,
    )


def list_tasks_tool(store: TaskStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return {"tasks": await store.list_tasks()}

    return Tool(
        name="list_tasks",
        description="列出所有任务（含状态、参与者、截止时间）。",
        parameters={"type": "object", "properties": {}, "required": []},
        risk="safe",
        category="任务",
        run_func=run,
    )


def submit_task_result_tool(store: TaskStore) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        user_id = (context or {}).get("user_id")
        return await store.submit_result(
            arguments.get("task_id", ""), user_id, arguments.get("reply", "")
        )

    return Tool(
        name="submit_task_result",
        description="记录某用户对某个任务的回复。参与者回复任务时调用。",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务 id"},
                "reply": {"type": "string", "description": "回复内容"},
            },
            "required": ["task_id", "reply"],
        },
        risk="safe",
        category="任务",
        run_func=run,
    )
