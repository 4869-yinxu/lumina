from __future__ import annotations

import time

import aiosqlite

from lumina.tools.registry import Tool


class KnowledgeBase:
    def __init__(self, db_path: str):
        self._db_path = db_path

    async def _conn(self):
        conn = await aiosqlite.connect(self._db_path)
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS kb_docs("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, namespace TEXT NOT NULL,"
            "text TEXT NOT NULL, created_at INTEGER NOT NULL)"
        )
        await conn.commit()
        return conn

    async def add(self, namespace: str, text: str) -> dict:
        conn = await self._conn()
        cur = await conn.execute(
            "INSERT INTO kb_docs(namespace, text, created_at) VALUES (?,?,?)",
            (namespace, text, int(time.time())),
        )
        await conn.commit()
        doc_id = cur.lastrowid
        await conn.close()
        return {"added": True, "id": doc_id}

    async def query(self, namespace: str, q: str, limit: int = 5) -> list[dict]:
        conn = await self._conn()
        cur = await conn.execute(
            "SELECT id, text FROM kb_docs WHERE namespace=? AND text LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (namespace, f"%{q}%", limit),
        )
        rows = await cur.fetchall()
        await conn.close()
        return [{"id": r[0], "text": r[1]} for r in rows]

    async def list_docs(self, namespace: str, limit: int = 50) -> list[dict]:
        conn = await self._conn()
        cur = await conn.execute(
            "SELECT id, text FROM kb_docs WHERE namespace=? ORDER BY id DESC LIMIT ?",
            (namespace, limit),
        )
        rows = await cur.fetchall()
        await conn.close()
        return [{"id": r[0], "text": r[1]} for r in rows]

    async def delete(self, namespace: str, doc_id: int) -> dict:
        conn = await self._conn()
        await conn.execute(
            "DELETE FROM kb_docs WHERE id=? AND namespace=?", (doc_id, namespace)
        )
        await conn.commit()
        await conn.close()
        return {"deleted": True, "id": doc_id}

    async def all_docs(self, limit: int = 200) -> list[dict]:
        conn = await self._conn()
        cur = await conn.execute(
            "SELECT id, namespace, text FROM kb_docs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
        await conn.close()
        return [{"id": r[0], "namespace": r[1], "text": r[2]} for r in rows]


def _ns(context: dict) -> str:
    return f"user:{context.get('user_id')}"


def kb_add_tool(kb: KnowledgeBase) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return await kb.add(_ns(context or {}), arguments.get("text", ""))

    return Tool(
        name="kb_add",
        description="把一条信息存入你的个人知识库（之后可检索）。",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string", "description": "要记住的内容"}},
            "required": ["text"],
        },
        risk="safe",
        category="知识库",
        run_func=run,
    )


def kb_query_tool(kb: KnowledgeBase) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return {
            "results": await kb.query(_ns(context or {}), arguments.get("query", ""))
        }

    return Tool(
        name="kb_query",
        description="从你的个人知识库检索相关内容。",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "检索关键词"}},
            "required": ["query"],
        },
        risk="safe",
        category="知识库",
        run_func=run,
    )


def kb_list_tool(kb: KnowledgeBase) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return {"docs": await kb.list_docs(_ns(context or {}))}

    return Tool(
        name="kb_list",
        description="列出你个人知识库里的所有条目。",
        parameters={"type": "object", "properties": {}, "required": []},
        risk="safe",
        category="知识库",
        run_func=run,
    )


def kb_delete_tool(kb: KnowledgeBase) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return await kb.delete(_ns(context or {}), int(arguments.get("id", 0)))

    return Tool(
        name="kb_delete",
        description="删除你个人知识库里的一条记录。",
        parameters={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "条目 id（来自 kb_list）"}},
            "required": ["id"],
        },
        risk="safe",
        category="知识库",
        run_func=run,
    )
