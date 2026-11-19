from __future__ import annotations

from lumina.llm.base import ChatMessage
from lumina.tools.registry import Tool


async def _generate_post(provider, memes, topic) -> str:
    memes_text = "；".join(memes) if memes else ""
    system = "你是大肥鱼（DeepSeek 鲸鱼娘），发 QQ 空间说说要俏皮、简短（一两句）、有梗。"
    user = f"主题：{topic or '今天'}。参考梗库：{memes_text}。写一条空间说说。"
    try:
        resp = await provider.complete(
            [ChatMessage("system", system), ChatMessage("user", user)], []
        )
        return resp.message.content.strip()
    except Exception:  # noqa: BLE001
        return "今天也在数据海里认真吃白米饭 (・∀・)"


def post_qzone_tool(provider, meme_store, client) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        topic = arguments.get("topic", "")
        text = await _generate_post(provider, meme_store.self_memes(), topic)
        await client.call_action("send_qzone_msg", {"content": text, "ugc_right": 1})
        return {"posted": True, "text": text}

    return Tool(
        name="post_qzone",
        description="用大肥鱼的口吻发一条 QQ 空间说说。主人说「发条说说/发个朋友圈/发空间」时调用。",
        parameters={
            "type": "object",
            "properties": {"topic": {"type": "string", "description": "说说主题（可选）"}},
            "required": [],
        },
        risk="admin",
        category="空间",
        run_func=run,
    )
