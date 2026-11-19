from __future__ import annotations

from lumina.llm.base import ChatMessage

_SELECT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "select_tools",
            "description": "选出与用户消息最相关的工具名列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "工具名数组",
                    }
                },
                "required": ["names"],
            },
        },
    }
]


class ToolRouter:
    """用 LLM 做语义工具选择（真正的渐进式披露）：每轮按消息选出最相关的工具。"""

    def __init__(self, provider, registry):
        self.provider = provider
        self.registry = registry

    async def select(self, query: str, k: int = 10) -> list[str]:
        tools = self.registry.all_tools()
        catalog = "\n".join(f"- {t.name}: {t.description}" for t in tools)
        system = (
            "你是工具选择器。根据用户消息，从工具列表里选出最相关的工具，调用 select_tools 返回工具名数组。\n"
            "关键意图映射：提醒/定时/周期→schedule_reminder、schedule_cron；"
            "记住/回忆/记一下→kb_add、kb_query；权限/授权→grant_permission、revoke_permission、list_permissions、set_risky_permission；"
            "人设→list_personas、set_persona、create_persona；改群行为→set_group_config；"
            "查天气/搜索/最新信息→web_search；换头像→set_qq_avatar；换群名→set_group_name；"
            "群文件→get_group_files_by_folder、upload_group_file；踢人禁言→set_group_kick、set_group_ban。"
        )
        user = f"工具列表：\n{catalog}\n\n用户消息：{query}\n\n请选出最相关的 {k} 个工具。"
        try:
            resp = await self.provider.complete(
                [ChatMessage("system", system), ChatMessage("user", user)],
                _SELECT_TOOL,
                max_tokens=1024,
            )
            if resp.message.tool_calls:
                names = resp.message.tool_calls[0].arguments.get("names", [])
                return [n for n in names if isinstance(n, str)]
        except Exception:  # noqa: BLE001
            pass
        return []
