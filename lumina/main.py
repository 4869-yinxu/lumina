from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import uvicorn

from lumina.agent.loop import Agent
from lumina.agent.knowledge import (
    KnowledgeBase,
    kb_add_tool,
    kb_delete_tool,
    kb_list_tool,
    kb_query_tool,
)
from lumina.agent.group_config import GroupConfig, set_group_config_tool
from lumina.agent.persona import (
    PersonaStore,
    WHALE_PERSONA,
    create_persona_tool,
    list_personas_tool,
    set_persona_tool,
)
from lumina.agent.permissions import (
    PermissionStore,
    grant_permission_tool,
    list_permissions_tool,
    revoke_permission_tool,
    set_risky_permission_tool,
)
from lumina.agent.plugins import PluginManager
from lumina.agent.skills import (
    SkillStore,
    create_skill_tool,
    delete_skill_tool,
    list_skills_tool,
)
from lumina.agent.task import (
    TaskStore,
    _set_task_context,
    create_task_tool,
    list_tasks_tool,
    submit_task_result_tool,
)
from lumina.agent.memes import (
    MemeStore,
    add_meme_tool,
    delete_meme_tool,
    list_memes_tool,
)
from lumina.agent.profile import UserProfileStore
from lumina.agent.qzone import post_qzone_tool
from lumina.agent.tool_retriever import ToolRetriever
from lumina.agent.reminders import (
    ReminderScheduler,
    _set_agent,
    cancel_reminder_tool,
    list_reminders_tool,
    schedule_cron_tool,
    schedule_reminder_tool,
    update_reminder_tool,
)
from lumina.agent.websearch import web_search_tool
from lumina.config import get_settings
from lumina.llm.provider_manager import ProviderManager, get_embedding_config, load_providers_config
from lumina.memory.store import MemoryStore
from lumina.mcp_client import McpClient, load_mcp_config, mcp_tool_to_agent_tool
from lumina.onebot.client import OneBotClient
from lumina.onebot.events import is_mentioned, parse_event
from lumina.onebot.schema import load_actions
from lumina.tools.discovery import search_tools_tool
from lumina.tools.registry import ToolRegistry
from lumina.web import app, install_log_ring, state

logger = logging.getLogger("lumina")

ACTIONS_PATH = Path(__file__).parent / "tools" / "snowluma_actions.json"


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    install_log_ring()

    settings = get_settings()
    data_dir = Path(settings.db_path).parent
    data_dir.mkdir(parents=True, exist_ok=True)

    # allowlist = env + 管理台保存的 JSON
    allowlist_path = data_dir / "allowlist.json"
    try:
        saved_allow = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        saved_allow = []
    allow_risky = set(settings.allow_risky) | set(saved_allow)

    actions = load_actions(ACTIONS_PATH)
    registry = ToolRegistry(actions, allow_risky=allow_risky)
    provider = ProviderManager.from_config(
        load_providers_config(settings.providers_config),
        env_defaults={
            "api_key": settings.deepseek_api_key,
            "base_url": settings.deepseek_base_url,
            "model": settings.deepseek_model,
        },
    )
    client = OneBotClient(
        http_url=settings.snowluma_http_url,
        ws_url=settings.snowluma_ws_url,
        http_token=settings.snowluma_http_token,
        ws_token=settings.snowluma_ws_token,
        reverse_host=settings.reverse_host,
        reverse_port=settings.reverse_port,
    )

    # built-in tools
    scheduler = ReminderScheduler(client, str(data_dir / "scheduler.db"), settings.timezone)
    registry.add(schedule_reminder_tool(scheduler))
    registry.add(schedule_cron_tool(scheduler))
    registry.add(list_reminders_tool(scheduler))
    registry.add(update_reminder_tool(scheduler))
    registry.add(cancel_reminder_tool(scheduler))

    group_config = GroupConfig(str(data_dir / "group_config.json"))
    registry.add(set_group_config_tool(group_config))

    persona_store = PersonaStore(str(data_dir / "personas.json"))
    if not persona_store.data.get("bindings", {}).get("global"):
        pid = persona_store._resolve_id("大肥鱼")
        if not pid:
            pid = persona_store.create("大肥鱼", WHALE_PERSONA)["id"]
        persona_store.bind(pid, "global", None)
        logger.info("seeded default persona 大肥鱼")
    registry.add(list_personas_tool(persona_store))
    registry.add(create_persona_tool(persona_store))
    registry.add(set_persona_tool(persona_store))

    permission_store = PermissionStore(str(data_dir / "permissions.json"))
    if not permission_store.data.get("developer"):
        permission_store.grant("2337302325", "developer")  # 4869 作为默认开发者
    registry.add(list_permissions_tool(permission_store))
    registry.add(grant_permission_tool(permission_store))
    registry.add(revoke_permission_tool(permission_store))
    registry.add(set_risky_permission_tool(registry, allowlist_path))

    skill_store = SkillStore(str(data_dir / "skills.json"))
    registry.add(list_skills_tool(skill_store))
    registry.add(create_skill_tool(skill_store))
    registry.add(delete_skill_tool(skill_store))

    task_store = TaskStore(str(data_dir / "tasks.db"))
    _set_task_context(client, task_store)
    registry.add(create_task_tool(task_store, scheduler))
    registry.add(list_tasks_tool(task_store))
    registry.add(submit_task_result_tool(task_store))

    meme_store = MemeStore(str(data_dir / "memes.json"))
    registry.add(list_memes_tool(meme_store))
    registry.add(add_meme_tool(meme_store))
    registry.add(delete_meme_tool(meme_store))

    profile_store = UserProfileStore(str(data_dir / "profiles.json"))
    registry.add(post_qzone_tool(provider, meme_store, client))

    kb = KnowledgeBase(str(data_dir / "knowledge.db"))
    registry.add(kb_add_tool(kb))
    registry.add(kb_query_tool(kb))
    registry.add(kb_list_tool(kb))
    registry.add(kb_delete_tool(kb))

    registry.add(web_search_tool(settings.tavily_api_key))
    registry.add(search_tools_tool(registry))

    # MCP servers：工具自动注入 registry（渐进披露，可用 search_tools 找到）
    mcp_clients = []
    for scfg in load_mcp_config(settings.mcp_config):
        mcp = McpClient(
            scfg.get("name", ""),
            scfg.get("command", ""),
            scfg.get("args", []) or [],
            scfg.get("env", {}) or {},
        )
        try:
            await mcp.start()
            tools = await mcp.list_tools()
            for t in tools:
                registry.add(
                    mcp_tool_to_agent_tool(mcp, t, risk=scfg.get("risk", "safe"))
                )
            mcp_clients.append(mcp)
            logger.info("MCP %s: loaded %d tools", scfg.get("name"), len(tools))
        except Exception as e:  # noqa: BLE001
            logger.warning("MCP %s start failed: %s", scfg.get("name"), e)

    # plugins：加载 plugins/ 目录
    plugin_manager = PluginManager(str(data_dir / "plugins"))
    plugin_manager.load(registry)

    # resolve bot self_id
    bot_id = 0
    try:
        login = await client.call_action("get_login_info", {})
        bot_id = int(login.get("user_id") or 0)
        logger.info("bot self_id = %s", bot_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("get_login_info failed: %s", e)

    memory = MemoryStore(settings.db_path)
    emb = get_embedding_config(load_providers_config(settings.providers_config))
    retriever = (
        ToolRetriever(emb[0], emb[1])
        if emb
        else ToolRetriever(settings.ollama_url, settings.embedding_model)
    )
    try:
        await retriever.build_index(registry.all_tools())
        logger.info("tool embedding index built: %d tools", len(registry.all_tools()))
    except Exception as e:  # noqa: BLE001
        logger.warning("tool index build failed: %s", e)
    agent = Agent(
        provider, registry, client, memory, settings,
        persona_store=persona_store, permission_store=permission_store,
        skill_store=skill_store, task_store=task_store, router=retriever,
        meme_store=meme_store, profile_store=profile_store,
    )
    _set_agent(agent)

    logger.info(
        "lumina started, reverse WS listening on %s:%s",
        settings.reverse_host,
        settings.reverse_port,
    )

    async def on_event(payload: dict) -> None:
        if payload.get("post_type") == "message":
            logger.info("EVENT %s", json.dumps(payload, ensure_ascii=False)[:800])
        event = parse_event(payload)
        if event is None:
            return
        if event.message_type == "group":
            if (
                group_config.reply_mode(event.group_id) == "mention_only"
                and bot_id
                and not is_mentioned(event, bot_id)
            ):
                return
        try:
            reply = await agent.handle_message(event)
            if event.message_type == "group":
                await client.call_action(
                    "send_group_msg",
                    {"group_id": event.group_id, "message": reply},
                )
            else:
                await client.call_action(
                    "send_private_msg",
                    {"user_id": event.user_id, "message": reply},
                )
        except Exception as e:  # noqa: BLE001
            logger.exception("handle message failed: %s", e)

    state.settings = settings
    state.registry = registry
    state.provider = provider
    state.bot_id = bot_id
    state.scheduler = scheduler
    state.kb = kb
    state.agent = agent
    state.memory = memory
    state.allowlist = allow_risky
    state.allowlist_path = allowlist_path
    state.providers_path = Path(settings.providers_config)
    state.persona = persona_store
    state.permission = permission_store
    state.skill = skill_store
    state.plugins = plugin_manager
    state.task = task_store
    state.meme = meme_store
    state.profile = profile_store
    state.mcp_clients = mcp_clients
    state.mcp_config_path = Path(settings.mcp_config)

    web_server = uvicorn.Server(
        uvicorn.Config(app, host="0.0.0.0", port=8081, log_level="warning")
    )
    await asyncio.gather(
        client.serve_ws(on_event),
        web_server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
