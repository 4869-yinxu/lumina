from __future__ import annotations

import asyncio

from lumina.tools.registry import Tool


def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    from ddgs import DDGS

    with DDGS() as d:
        out = []
        for r in d.text(query, max_results=max_results):
            out.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
            )
        return out


def _tavily_search(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    import httpx

    r = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": api_key, "query": query, "max_results": max_results},
        timeout=15.0,
    )
    r.raise_for_status()
    data = r.json()
    return [
        {"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")}
        for x in data.get("results", [])
    ]


async def search(arguments: dict, tavily_api_key: str = "") -> dict:
    query = (arguments.get("query") or "").strip()
    if not query:
        return {"error": "搜索关键词为空"}
    try:
        if tavily_api_key:
            results = await asyncio.to_thread(_tavily_search, query, tavily_api_key, 5)
        else:
            results = await asyncio.to_thread(_ddg_search, query, 5)
        return {"query": query, "results": results}
    except ImportError:
        return {"error": "搜索功能不可用（未安装 ddgs）"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"搜索失败：{e}"}


def web_search_tool(tavily_api_key: str = "") -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return await search(arguments, tavily_api_key)

    return Tool(
        name="web_search",
        description="联网搜索网页，返回标题、链接和摘要。用于需要最新信息、外部资料或事实核查的问题。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["query"],
        },
        risk="safe",
        category="搜索",
        run_func=run,
    )
