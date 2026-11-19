from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from lumina.config import Settings
from lumina.llm.base import ChatMessage, LLMProvider
from lumina.memory.store import MemoryStore
from lumina.onebot.client import OneBotClient
from lumina.onebot.events import MessageEvent
from lumina.tools.registry import ToolRegistry

SYSTEM_PROMPT = (
    "你是这个 QQ 群里的 AI 助手，也是群友的好朋友。说话要像真人网友，别像客服机器人、别像写小作文。\n"
    "【说话风格】口语化、自然、有温度；能随语境开玩笑、接梗、用表情/颜文字；"
    "回复要短，一般一两句话就够，别人没要求就别展开、别列一堆点；别机械复述、别每句都「好的/明白」开头。\n"
    "【热梗/黑话】遇到不懂的网络热梗、缩写、黑话，先用 web_search 搜一下意思，理解了再回应，别瞎猜装懂。\n"
    "【定时提醒】用户提「X分钟/小时后提醒」「X点提醒」「稍后提醒」「@我提醒」等，"
    "必须调用 schedule_reminder（把「我」换成发送者 user_id，时间换算成 delay_seconds 秒，群号用当前群），不能只口头答应。\n"
    "【周期任务（最高优先级）】用户提「每天/每周X点」「每天早上/每晚」「周期性」等重复任务时，"
    "必须立即调用 schedule_cron 工具：cron 为「分 时 日 月 周」（每天8点='0 8 * * *'、每天23点='0 23 * * *'），"
    "task 参数写清要执行的任务内容。严禁只口头答应「已设定」却不真正调用工具。\n"
    "【任务管理】用户要「改/删除/列出提醒任务」时，用 update_reminder / cancel_reminder / list_reminders。\n"
    "【知识库】用户说「记住/记一下/存一下」+ 内容用 kb_add；回忆之前的事用 kb_query。\n"
    "【配置】用户要求改本群行为（如「此群只有@我才回复」）时用 set_group_config。\n"
    "【人设】用户要求「设人设/换人设/这个人设」时，用 list_personas / set_persona / create_persona 工具。\n"
    "【权限】最高权限者说「给XX升vip/svip」「取消XX的权限」「查权限」时，用 grant_permission / revoke_permission / list_permissions 工具；"
    "说「开启/关闭某工具的权限」时用 set_risky_permission 工具。\n"
    "群消息以「[昵称] 内容」标记发言者，要能区分不同成员。每次会告知当前群、发送者、当前时间。"
    "工具是渐进披露的，需要时用 search_tools 搜索。"
)

META_TOOLS = {
    "send_group_msg",
    "send_private_msg",
    "search_tools",
    "web_search",
}

ALWAYS_ON = {
    "send_group_msg",
    "send_private_msg",
    "send_msg",
    "get_msg",
    "get_group_list",
    "get_group_info",
    "get_group_member_list",
    "get_group_member_info",
    "get_stranger_info",
    "get_friend_list",
    "get_login_info",
    "get_status",
    "set_qq_avatar",
    "set_group_portrait",
    "set_group_name",
    "schedule_reminder",
    "schedule_cron",
    "list_reminders",
    "update_reminder",
    "cancel_reminder",
    "set_group_config",
    "list_personas",
    "create_persona",
    "set_persona",
    "list_permissions",
    "grant_permission",
    "revoke_permission",
    "set_risky_permission",
    "kb_add",
    "kb_query",
    "kb_list",
    "kb_delete",
    "web_search",
    "search_tools",
}


class Agent:
    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        client: OneBotClient,
        memory: MemoryStore,
        settings: Settings,
        persona_store=None,
        permission_store=None,
        skill_store=None,
        task_store=None,
        router=None,
        meme_store=None,
        profile_store=None,
    ):
        self.provider = provider
        self.registry = registry
        self.client = client
        self.memory = memory
        self.settings = settings
        self.persona_store = persona_store
        self.permission_store = permission_store
        self.skill_store = skill_store
        self.task_store = task_store
        self.router = router
        self.meme_store = meme_store
        self.profile_store = profile_store
        self._group_names: dict[int, str] = {}

    def _system(self, context_note: str, group_id, user_id, skill_prompts=None, task_note="") -> str:
        parts = []
        if self.persona_store:
            persona = self.persona_store.resolve(group_id, user_id)
            if persona:
                parts.append(f"【当前人设】{persona}")
        for sp in skill_prompts or []:
            parts.append(f"【技能】{sp}")
        if self.meme_store:
            self_memes = self.meme_store.self_memes()
            if self_memes:
                parts.append("【梗库】" + "；".join(self_memes))
            person_memes = self.meme_store.person_memes(user_id)
            if person_memes:
                parts.append("【对当前用户的梗】" + "；".join(person_memes))
        if self.profile_store:
            facts = self.profile_store.get_facts(user_id)
            if facts:
                parts.append("【对当前用户的画像】" + "；".join(facts))
        if task_note:
            parts.append(task_note)
        parts.append(SYSTEM_PROMPT)
        parts.append(context_note)
        return "\n\n".join(parts)

    def _scope(self, event: MessageEvent) -> str:
        return f"{event.message_type}:{event.group_id or event.user_id}"

    async def _resolve_group_name(self, event: MessageEvent) -> str:
        if event.message_type != "group":
            return ""
        gid = event.group_id
        if gid in self._group_names:
            return self._group_names[gid]
        try:
            data = await self.client.call_action("get_group_info", {"group_id": gid})
            name = data.get("group_name") or str(gid)
        except Exception:  # noqa: BLE001
            name = str(gid)
        self._group_names[gid] = name
        return name

    def _context(self, event: MessageEvent, group_name: str, level: str) -> str:
        now = datetime.now(ZoneInfo(self.settings.timezone)).strftime("%Y-%m-%d %H:%M:%S")
        label = event.sender_nickname or str(event.user_id)
        who = f"{label}（{event.user_id}，权限：{level}）"
        ctx = f"当前时间：{now}。"
        if event.message_type == "group":
            ctx += f"当前群：{group_name}（群号 {event.group_id}）。发送者：{who}。"
            ctx += (
                f"例如：用户说「2分钟后@我提醒我做作业」→ 调 schedule_reminder(group_id={event.group_id}, "
                f"user_id={event.user_id}, delay_seconds=120, message='提醒做作业')。"
                f"用户说「每天晚上11点查天气提醒我」→ 调 schedule_cron(group_id={event.group_id}, "
                f"user_id={event.user_id}, cron='0 23 * * *', task='查明天天气并给出带伞穿衣建议')。"
                f"绝不能只回复「已设定」而不调用工具。"
            )
        else:
            ctx += f"当前私聊。发送者：{who}。"
        img_urls = [
            seg.get("data", {}).get("url", "")
            for seg in event.message
            if seg.get("type") == "image" and seg.get("data", {}).get("url")
        ]
        if img_urls:
            ctx += (
                "本消息包含图片，URL 为：" + "、".join(img_urls) +
                "。如需用这张图（如 set_qq_avatar 设为头像、set_group_portrait 设为群头像），"
                "把该 URL 作为 file 参数传入。"
            )
        return ctx

    async def _retrieve_tools(self, text: str) -> set | None:
        """渐进式披露：核心工具常驻 + 长尾工具按语义动态检索。失败返回 None（回退 ALWAYS_ON）。"""
        if self.router is None:
            return None
        try:
            names = await self.router.select(text, k=10)
            return set(ALWAYS_ON) | set(names)
        except Exception:  # noqa: BLE001
            return None

    async def _run_loop(
        self,
        messages: list[ChatMessage],
        context: dict,
        disclosed: set | None = None,
    ) -> str:
        level = context.get("level", "developer")
        disclosed = set(disclosed) if disclosed is not None else set(ALWAYS_ON)
        tools = self.registry.openai_tools_for(disclosed, level)
        for _ in range(self.settings.max_steps):
            resp = await self.provider.complete(messages, tools)
            msg = resp.message
            if not msg.tool_calls:
                return msg.content or "（无回复）"
            messages.append(msg)
            for tc in msg.tool_calls:
                tool = self.registry.get(tc.name, level)
                if tool is None:
                    result = {"error": f"工具 {tc.name} 不可用或无权限"}
                else:
                    try:
                        result = await tool.run(tc.arguments, self.client, context)
                    except Exception as e:  # noqa: BLE001
                        result = {"error": str(e)}
                if tc.name == "search_tools":
                    for m in result.get("matches", []):
                        disclosed.add(m["name"])
                    tools = self.registry.openai_tools_for(disclosed, level)
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=json.dumps(result, ensure_ascii=False)[:4000],
                        tool_call_id=tc.id,
                    )
                )
        return "（已达最大步数，未完成）"

    async def _image_to_base64(self, seg: dict) -> str | None:
        data = seg.get("data", {}) or {}
        url = data.get("url", "")
        file_id = data.get("file_id", "")
        file = data.get("file", "")
        ext = Path(file or "").suffix.lower().lstrip(".")
        mime = {"png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(
            ext, "image/jpeg"
        )

        async def fetch(u: str) -> str:
            async with httpx.AsyncClient(timeout=15.0) as hc:
                r = await hc.get(u)
                r.raise_for_status()
                return f"data:{mime};base64," + base64.b64encode(r.content).decode()

        if url and url.startswith("http"):
            try:
                return await fetch(url)
            except Exception:  # noqa: BLE001
                pass
        try:
            result = await self.client.call_action(
                "get_image", {"file": file, "file_id": file_id}
            )
            if isinstance(result, dict):
                for key in ("base64", "data", "image", "content", "url"):
                    v = result.get(key)
                    if isinstance(v, str) and v:
                        if v.startswith("http"):
                            return await fetch(v)
                        if len(v) > 100:
                            return f"data:{mime};base64," + v
            elif isinstance(result, str) and result.startswith("http"):
                return await fetch(result)
        except Exception:  # noqa: BLE001
            pass
        return None

    async def _collect_images(self, event: MessageEvent) -> list[str]:
        """收集消息里的图片（含 reply 引用的原消息里的图）并转 base64。"""
        image_b64s: list[str] = []
        segments = list(event.message)

        for seg in event.message:
            if seg.get("type") != "reply":
                continue
            msg_id = seg.get("data", {}).get("id") or seg.get("data", {}).get("message_id")
            if not msg_id:
                continue
            try:
                quoted = await self.client.call_action(
                    "get_msg", {"message_id": int(msg_id)}
                )
                for qseg in quoted.get("message") or []:
                    if qseg.get("type") == "image":
                        segments.append(qseg)
            except Exception:  # noqa: BLE001
                continue

        for seg in segments:
            if seg.get("type") == "image":
                b64 = await self._image_to_base64(seg)
                if b64:
                    image_b64s.append(b64)
        return image_b64s

    async def handle_message(self, event: MessageEvent) -> str:
        scope = self._scope(event)
        label = event.sender_nickname or str(event.user_id)
        text = event.raw_message or "[图片]"
        text_content = (
            f"[{label}] {text}" if event.message_type == "group" else text
        )
        await self.memory.append(scope, "user", text_content)

        image_b64s = await self._collect_images(event)

        level = (
            self.permission_store.get_level(event.user_id)
            if self.permission_store
            else "developer"
        )
        context = {
            "scope": scope,
            "user_id": event.user_id,
            "group_id": event.group_id,
            "nickname": label,
            "level": level,
        }

        group_name = await self._resolve_group_name(event)
        skill_prompts = (
            [s["prompt"] for s in self.skill_store.match(event.raw_message)]
            if self.skill_store
            else []
        )
        task_note = ""
        if self.task_store:
            active = await self.task_store.active_tasks(event.user_id)
            if active:
                task_note = "你当前有这些待回复任务：" + "；".join(
                    f"[{t['id']}] {t['description']}" for t in active
                ) + "。对方若是对任务的回复，用 submit_task_result(task_id=对应id, reply=内容) 记录。"
        system = self._system(
            self._context(event, group_name, level),
            event.group_id,
            event.user_id,
            skill_prompts,
            task_note,
        )
        history = await self.memory.recent(scope)
        if image_b64s:
            parts: list[dict] = [{"type": "text", "text": text_content}]
            for b64 in image_b64s:
                parts.append(
                    {"type": "image_url", "image_url": {"url": b64}}
                )
            history[-1] = ChatMessage(role="user", content=parts)
        messages = [ChatMessage(role="system", content=system)] + history

        reply = await self._run_loop(messages, context, await self._retrieve_tools(event.raw_message))
        await self.memory.append(scope, "assistant", reply)

        if self.profile_store:
            try:
                should = self.profile_store.bump(event.user_id)
                if should:
                    hist = "\n".join(
                        f"{m.role}: {m.content}" for m in await self.memory.recent(scope, limit=20)
                    )
                    from lumina.agent.profile import extract_facts
                    facts = await extract_facts(
                        self.provider, self.profile_store.get_facts(event.user_id), hist
                    )
                    self.profile_store.set_facts(event.user_id, facts)
            except Exception:  # noqa: BLE001
                pass

        return reply

    async def run_task(self, task_prompt: str, context: dict) -> str:
        now = datetime.now(ZoneInfo(self.settings.timezone)).strftime("%Y-%m-%d %H:%M:%S")
        note = f"这是一个定时任务，当前时间：{now}。请执行这个任务，用工具获取需要的信息（如天气用 web_search），完成后给出结果。"
        system = self._system(note, context.get("group_id"), context.get("user_id"))
        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=task_prompt),
        ]
        return await self._run_loop(messages, context or {}, await self._retrieve_tools(task_prompt))
