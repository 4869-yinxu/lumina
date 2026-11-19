from __future__ import annotations

import time

import aiosqlite

from lumina.llm.base import ChatMessage


class MemoryStore:
    def __init__(self, db_path: str):
        self._db_path = db_path

    async def _conn(self):
        conn = await aiosqlite.connect(self._db_path)
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "scope TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,"
            "ts INTEGER NOT NULL)"
        )
        await conn.commit()
        return conn

    async def append(self, scope: str, role: str, content: str) -> None:
        conn = await self._conn()
        await conn.execute(
            "INSERT INTO messages (scope, role, content, ts) VALUES (?, ?, ?, ?)",
            (scope, role, content, int(time.time())),
        )
        await conn.commit()
        await conn.close()

    async def recent(self, scope: str, limit: int = 20) -> list[ChatMessage]:
        conn = await self._conn()
        cur = await conn.execute(
            "SELECT role, content FROM messages WHERE scope = ? "
            "ORDER BY id DESC LIMIT ?",
            (scope, limit),
        )
        rows = await cur.fetchall()
        await conn.close()
        rows = list(reversed(rows))
        return [ChatMessage(role=r, content=c) for r, c in rows]

    async def clear(self, scope: str) -> None:
        conn = await self._conn()
        await conn.execute("DELETE FROM messages WHERE scope = ?", (scope,))
        await conn.commit()
        await conn.close()

    async def scopes(self) -> list[str]:
        conn = await self._conn()
        cur = await conn.execute("SELECT DISTINCT scope FROM messages ORDER BY scope")
        rows = await cur.fetchall()
        await conn.close()
        return [r[0] for r in rows]
