from __future__ import annotations

from lumina.tools.registry import Tool, ToolRegistry


def search_tools_tool(registry: ToolRegistry) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        query = arguments.get("query", "") or ""
        category = arguments.get("category", "") or ""
        level = (context or {}).get("level", "developer")
        matches = registry.search(query, category, level)
        matches = sorted(matches, key=lambda t: t.name)[:15]
        return {
            "query": query,
            "category": category,
            "count": len(matches),
            "matches": [
                {
                    "name": t.name,
                    "category": t.category,
                    "description": t.description,
                    "parameters": t.parameters,
                }
                for t in matches
            ],
        }

    return Tool(
        name="search_tools",
        description=(
            "当需要的功能不在当前可用工具里时，用本工具按关键词或分类搜索更多可用工具。"
            "返回匹配的工具名、说明和参数；之后即可用返回的工具名调用这些工具。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "关键词，匹配工具名或描述"},
                "category": {
                    "type": "string",
                    "description": "分类名，如 消息/群管理/群信息/群文件/群相册/空间/好友/信息/系统表情/流式接口/请求/扩展",
                },
            },
            "required": [],
        },
        risk="safe",
        category="工具",
        run_func=run,
    )
