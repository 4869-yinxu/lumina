from __future__ import annotations

import math

import httpx


class ToolRetriever:
    """基于 bge-m3 embedding 的语义工具检索（真正的渐进式披露，无额外 LLM 调用）。"""

    def __init__(self, base_url: str, model: str = "bge-m3"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._names: list[str] = []
        self._vecs: list[list[float]] = []

    @staticmethod
    def _norm(v):
        n = math.sqrt(sum(x * x for x in v))
        return [x / n for x in v] if n else v

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
            )
            r.raise_for_status()
            return r.json()["embeddings"]

    async def build_index(self, tools) -> None:
        texts = [f"{t.name} {t.description}" for t in tools]
        embeddings = await self._embed(texts)
        self._names = [t.name for t in tools]
        self._vecs = [self._norm(v) for v in embeddings]

    async def select(self, query: str, k: int = 10) -> list[str]:
        if not self._names:
            return []
        q = self._norm((await self._embed([query]))[0])
        scores = [
            (sum(a * b for a, b in zip(q, v)), n)
            for n, v in zip(self._names, self._vecs)
        ]
        scores.sort(reverse=True)
        return [n for _, n in scores[:k]]
