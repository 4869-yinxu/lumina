from __future__ import annotations

import json
import logging
import secrets
import time
from collections import deque
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from lumina.agent.loop import ALWAYS_ON
from lumina.llm.provider_manager import ProviderManager
from lumina.mcp_client import McpClient, load_mcp_config, mcp_tool_to_agent_tool
from lumina.onebot.events import MessageEvent

START_TIME = time.time()
LOG_BUFFER: deque[str] = deque(maxlen=300)
AUTH_TOKENS: set[str] = set()
DIST_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "dist"


class RingHandler(logging.Handler):
    def emit(self, record):
        try:
            LOG_BUFFER.append(self.format(record))
        except Exception:  # noqa: BLE001
            pass


def install_log_ring() -> None:
    handler = RingHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    for name in ("lumina", "websockets.server"):
        logging.getLogger(name).addHandler(handler)


class AppState:
    def __init__(self):
        self.bot_id = 0
        self.settings = None
        self.registry = None
        self.provider = None
        self.scheduler = None
        self.kb = None
        self.agent = None
        self.memory = None
        self.allowlist: set[str] = set()
        self.allowlist_path = None
        self.providers_path = None
        self.persona = None
        self.permission = None
        self.skill = None
        self.plugins = None
        self.mcp_clients = []
        self.mcp_config_path = None
        self.task = None
        self.meme = None


state = AppState()
app = FastAPI(title="lumina")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path.startswith("/api") and path != "/api/login":
            pw = state.settings.admin_password if state.settings else ""
            if pw:
                token = request.headers.get("authorization", "").removeprefix("Bearer ")
                if token not in AUTH_TOKENS:
                    return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)


app.add_middleware(AuthMiddleware)


def _env_defaults() -> dict:
    s = state.settings
    return {
        "api_key": s.deepseek_api_key,
        "base_url": s.deepseek_base_url,
        "model": s.deepseek_model,
    }


def _rebuild_provider(cfg: dict):
    new = ProviderManager.from_config(cfg, env_defaults=_env_defaults())
    state.provider = new
    if state.agent is not None:
        state.agent.provider = new
    return new


def _save_providers(cfg: dict):
    if state.providers_path:
        state.providers_path.write_text(
            yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
    return _rebuild_provider(cfg)


def _load_cfg() -> dict:
    try:
        if state.providers_path and state.providers_path.exists():
            return yaml.safe_load(state.providers_path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        pass
    return {"providers": []}


# ------------------------------------------------------------------ auth/status
@app.post("/api/login")
async def login(req: Request):
    body = await req.json()
    pw = state.settings.admin_password if state.settings else ""
    if not pw or body.get("password") == pw:
        token = secrets.token_hex(16)
        AUTH_TOKENS.add(token)
        return {"token": token}
    return JSONResponse({"detail": "wrong password"}, status_code=401)


@app.get("/api/status")
async def status():
    tools = state.registry.all_tools() if state.registry else []
    by_risk = {"safe": 0, "risky": 0, "forbidden": 0}
    for t in tools:
        by_risk[t.risk] = by_risk.get(t.risk, 0) + 1
    desc_map = {t.name: t.description for t in tools}
    return {
        "bot_id": state.bot_id,
        "uptime_seconds": int(time.time() - START_TIME),
        "model": state.settings.deepseek_model if state.settings else "",
        "provider": getattr(state.provider, "default", ""),
        "tools_total": len(tools),
        "tools_by_risk": by_risk,
        "always_on": sorted(ALWAYS_ON),
        "always_on_zh": [desc_map.get(n, n) for n in sorted(ALWAYS_ON)],
        "allow_risky": sorted(state.allowlist),
    }


@app.get("/api/tools")
async def tools_list():
    cats: dict[str, list] = {}
    for t in state.registry.all_tools():
        cats.setdefault(t.category or "其他", []).append(
            {
                "name": t.name,
                "risk": t.risk,
                "description": t.description,
                "enabled": state.registry._enabled(t),
            }
        )
    return {"categories": {k: cats[k] for k in sorted(cats)}}


# ------------------------------------------------------------------- providers
@app.get("/api/providers")
async def providers():
    cfg = _load_cfg()
    items = cfg.get("providers", []) or []
    return {
        "providers": [
            {
                "id": p.get("id"),
                "model": p.get("model", ""),
                "type": p.get("type", "chat"),
                "base_url": p.get("base_url", ""),
            }
            for p in items
        ],
        "default": cfg.get("default_provider", ""),
        "fallback": cfg.get("fallback", []),
    }


@app.post("/api/providers")
async def add_provider(req: Request):
    body = await req.json()
    cfg = _load_cfg()
    providers = (cfg or {}).get("providers", []) or []
    providers = [p for p in providers if p.get("id") != body.get("id")]
    providers.append(
        {
            "id": body.get("id"),
            "base_url": body.get("base_url", ""),
            "api_key": body.get("api_key", ""),
            "model": body.get("model", ""),
            "type": body.get("type", "chat"),
        }
    )
    cfg = cfg or {}
    cfg["providers"] = providers
    cfg.setdefault("default_provider", body.get("id"))
    _save_providers(cfg)
    return {"ok": True}


@app.put("/api/providers/{pid}")
async def update_provider(pid: str, req: Request):
    body = await req.json()
    cfg = _load_cfg()
    providers = (cfg or {}).get("providers", []) or []
    for p in providers:
        if p.get("id") == pid:
            for key in ("base_url", "api_key", "model", "type"):
                if key in body:
                    p[key] = body[key]
            break
    cfg["providers"] = providers
    _save_providers(cfg)
    return {"ok": True}


@app.delete("/api/providers/{pid}")
async def delete_provider(pid: str):
    cfg = _load_cfg()
    providers = (cfg or {}).get("providers", []) or []
    providers = [p for p in providers if p.get("id") != pid]
    cfg = cfg or {}
    cfg["providers"] = providers
    if cfg.get("default_provider") == pid and providers:
        cfg["default_provider"] = providers[0]["id"]
    _save_providers(cfg)
    return {"ok": True}


# -------------------------------------------------------------------- allowlist
@app.post("/api/allowlist")
async def update_allowlist(req: Request):
    body = await req.json()
    names = set(body.get("allow") or [])
    state.allowlist = names
    state.registry.set_allow_risky(names)
    if state.allowlist_path:
        try:
            state.allowlist_path.write_text(json.dumps(sorted(names)), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "allow": sorted(names)}


# ---------------------------------------------------------------- conversations
@app.get("/api/conversations")
async def conversations():
    if state.memory:
        return {"scopes": await state.memory.scopes()}
    return {"scopes": []}


@app.get("/api/conversations/{scope}")
async def conversation_messages(scope: str):
    if state.memory:
        msgs = await state.memory.recent(scope, limit=100)
        return {"scope": scope, "messages": [{"role": m.role, "content": m.content} for m in msgs]}
    return {"scope": scope, "messages": []}


@app.delete("/api/conversations/{scope}")
async def conversation_clear(scope: str):
    if state.memory:
        await state.memory.clear(scope)
        return {"cleared": True, "scope": scope}
    return {"error": "memory not ready"}


@app.get("/api/tasks")
async def tasks_list():
    if state.task:
        return {"tasks": await state.task.list_tasks()}
    return {"tasks": []}


@app.get("/api/memes")
async def memes_list():
    if state.meme:
        return {"memes": state.meme.list_all()}
    return {"memes": {"self": [], "person": {}}}


@app.post("/api/memes")
async def memes_add(req: Request):
    body = await req.json()
    if state.meme:
        return state.meme.add(body.get("text", ""), body.get("user_id"))
    return {"error": "meme not ready"}


@app.delete("/api/memes")
async def memes_delete(req: Request):
    body = await req.json()
    if state.meme:
        return state.meme.delete(body.get("text", ""))
    return {"error": "meme not ready"}


# ------------------------------------------------------------ reminders + kb
@app.get("/api/reminders")
async def reminders():
    if state.scheduler:
        return {"reminders": state.scheduler.list_jobs()}
    return {"reminders": []}


@app.post("/api/reminders/{job_id}/cancel")
async def cancel_reminder(job_id: str):
    if state.scheduler:
        return state.scheduler.cancel(job_id)
    return {"error": "scheduler not ready"}


@app.get("/api/kb")
async def kb_docs():
    if state.kb:
        return {"docs": await state.kb.all_docs()}
    return {"docs": []}


@app.post("/api/kb")
async def kb_add(req: Request):
    body = await req.json()
    text = (body.get("text") or "").strip()
    ns = body.get("namespace") or "manual"
    if not text or not state.kb:
        return {"error": "empty"}
    return await state.kb.add(ns, text)


@app.delete("/api/kb/{doc_id}")
async def kb_delete(doc_id: int):
    if not state.kb:
        return {"error": "kb not ready"}
    conn = await state.kb._conn()
    await conn.execute("DELETE FROM kb_docs WHERE id=?", (doc_id,))
    await conn.commit()
    await conn.close()
    return {"deleted": True, "id": doc_id}


# ------------------------------------------------------------------------ chat
@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    text = (body.get("message") or "").strip()
    if not text or not state.agent:
        return {"reply": ""}
    event = MessageEvent(
        "private", 0, None, [], text, int(time.time() * 1000), sender_nickname="web"
    )
    try:
        reply = await state.agent.handle_message(event)
    except Exception as e:  # noqa: BLE001
        reply = f"错误：{e}"
    return {"reply": reply}


@app.get("/api/logs")
async def logs():
    return {"logs": list(LOG_BUFFER)}


@app.get("/api/personas")
async def personas():
    if state.persona:
        return {
            "personas": state.persona.list_personas(),
            "bindings": state.persona.data.get("bindings", {}),
        }
    return {"personas": [], "bindings": {}}


@app.post("/api/personas")
async def create_persona(req: Request):
    body = await req.json()
    if state.persona:
        return state.persona.create(body.get("name", ""), body.get("prompt", ""))
    return {"error": "persona not ready"}


@app.delete("/api/personas/{pid}")
async def delete_persona(pid: str):
    if state.persona:
        return state.persona.delete(pid)
    return {"error": "persona not ready"}


@app.put("/api/personas/{pid}")
async def update_persona(pid: str, req: Request):
    body = await req.json()
    if state.persona:
        return state.persona.update(pid, body.get("name"), body.get("prompt"))
    return {"error": "persona not ready"}


@app.get("/api/permissions")
async def permissions():
    if state.permission:
        return {"permissions": state.permission.list_permissions()}
    return {"permissions": {}}


@app.post("/api/permissions")
async def permission_grant(req: Request):
    body = await req.json()
    if state.permission:
        return state.permission.grant(body.get("user_id"), body.get("level", ""))
    return {"error": "permission not ready"}


@app.get("/api/skills")
async def skills_list():
    if state.skill:
        return {"skills": state.skill.list_skills()}
    return {"skills": []}


@app.post("/api/skills")
async def skills_create(req: Request):
    body = await req.json()
    if state.skill:
        return state.skill.create(
            body.get("name", ""), body.get("trigger", ""), body.get("prompt", "")
        )
    return {"error": "skill not ready"}


@app.delete("/api/skills/{sid}")
async def skills_delete(sid: str):
    if state.skill:
        return state.skill.delete(sid)
    return {"error": "skill not ready"}


@app.get("/api/plugins")
async def plugins_list():
    if state.plugins:
        return {"plugins": state.plugins.list_plugins()}
    return {"plugins": []}


@app.post("/api/plugins/{name}/start")
async def plugin_start(name: str):
    if state.plugins:
        return await state.plugins.start(name)
    return {"error": "plugins not ready"}


@app.post("/api/plugins/{name}/stop")
async def plugin_stop(name: str):
    if state.plugins:
        return await state.plugins.stop(name)
    return {"error": "plugins not ready"}


@app.get("/api/mcp")
async def mcp_list():
    servers = load_mcp_config(str(state.mcp_config_path) if state.mcp_config_path else "")
    loaded = {c.name for c in state.mcp_clients}
    return {"servers": [{"name": s.get("name"), "command": s.get("command"), "loaded": s.get("name") in loaded} for s in servers]}


@app.post("/api/mcp")
async def mcp_add(req: Request):
    body = await req.json()
    name = body.get("name", "")
    command = body.get("command", "")
    args = body.get("args", []) or []
    env = body.get("env", {}) or {}
    # 追加到配置
    if state.mcp_config_path:
        import yaml as _yaml
        servers = load_mcp_config(str(state.mcp_config_path))
        servers = [s for s in servers if s.get("name") != name]
        servers.append({"name": name, "command": command, "args": args, "env": env, "risk": "safe"})
        state.mcp_config_path.write_text(
            _yaml.safe_dump({"servers": servers}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    # 热连接
    client = McpClient(name, command, args, env)
    try:
        await client.start()
        for t in await client.list_tools():
            state.registry.add(mcp_tool_to_agent_tool(client, t, risk="safe"))
        state.mcp_clients.append(client)
        return {"ok": True, "name": name}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


@app.post("/api/mcp/{name}/stop")
async def mcp_stop(name: str):
    for c in state.mcp_clients:
        if c.name == name:
            await c.close()
            state.mcp_clients.remove(c)
            return {"stopped": True, "name": name}
    return {"error": f"MCP {name} 未运行"}


# ----------------------------------------------------------------- static SPA
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


@app.get("/")
async def index():
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("dashboard not built. run: cd dashboard && npm install && npm run build")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    f = DIST_DIR / full_path
    if f.is_file():
        return FileResponse(f)
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("dashboard not built")
