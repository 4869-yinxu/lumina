# Lumina 🐋

一个跑在 [SnowLuma](https://github.com/SnowLuma/SnowLuma)（OneBot 11）之上的 QQ 智能体（agent），用 DeepSeek 驱动，自带「大肥鱼 / 鲸鱼娘」人设。

不是另一个聊天机器人，而是一个真正的 **harness agent**：模型按意图动态选工具、多步推理执行，可扩展 MCP / 技能 / 插件。

## 功能特性

- **Harness Agent**：ReAct 多步循环 + 函数调用，模型动态决定调哪个工具、按什么顺序。
- **198 个 SnowLuma 动作**：消息 / 群管理 / 群文件 / 群相册 / QQ 空间 / 闪传等，按 `safe / risky / forbidden` 分级。
- **渐进式披露**：核心工具常驻 + 长尾工具用 bge-m3 语义检索按需挂载。
- **多模型供应商**：`providers.yaml` 区分对话 / 嵌入 / 视觉模型，可热切换、失败回退。
- **定时任务**：一次性提醒 + cron 周期任务（APScheduler + SQLite 持久化），周期任务由 agent 真正执行（联网查天气等）。
- **人设（Persona）**：多人设、全局/每群/每用户三层绑定，内置「大肥鱼」默认人设。
- **梗库（Meme）**：可增删改的口头禅/梗，对话里就能加，实时生效。
- **人物画像（Profile）**：从对话自动抽取用户稳定事实，每 N 条消息增量更新。
- **知识库（KB）**：每用户命名空间的长期记忆，`记住 / 回忆`。
- **多参与者任务**：私信通知多人完成任务、截止自动汇总反馈。
- **权限分级**：`user / vip / svip / developer`，工具级拦截 + 上下文注入，对话可授予/撤销。
- **技能（Skills）/ 插件（Plugins）/ MCP**：均可扩展。
- **管理台**：Vue3 + Vuetify，登录鉴权，管理供应商/工具/人设/梗库/定时任务/知识库/对话/聊天测试。
- **多模态**：图片消息喂给 DeepSeek 视觉模型。

## 快速开始

### 依赖

- Docker + Docker Compose
- 一个 [SnowLuma](https://github.com/SnowLuma/SnowLuma) 实例（跑 QQ / OneBot 11）
- DeepSeek API Key
- 本地 Ollama（跑 bge-m3 做语义检索）

### 部署

```bash
git clone https://github.com/<你的用户名>/lumina.git
cd lumina

# 1. 配置环境变量（真实密钥，已 gitignore，不会提交）
cp .env.example .env
# 编辑 .env，填入 DeepSeek key、SnowLuma token、Tavily key、admin 密码

# 2. 建共享网络并启动
docker network create botnet || true
docker compose up -d --build
```

### 接入 SnowLuma

SnowLuma 反向 WS 连到 Lumina：把 SnowLuma 的 `onebot_<账号>.json` 里 `networks.wsClients` 的 `url` 改成 `ws://lumina:8080/ws`，然后重启 SnowLuma。

管理台：`http://127.0.0.1:8081`（默认密码在 `.env` 的 `LUMINA_ADMIN_PASSWORD`）。

## 配置说明

| 文件 | 作用 |
|---|---|
| `.env` | 密钥与基础配置（`LUMINA_*` 前缀） |
| `providers.yaml` | 多模型供应商（chat / embedding / vision） |
| `mcp_servers.yaml` | MCP 服务器（stdio） |
| `data/` | 运行时数据（记忆/定时/知识库/人设/梗库/画像等，gitignore） |

## 目录结构

```
lumina/
├── lumina/            # Python 后端（FastAPI + 反向 WS + agent）
│   ├── agent/         # ReAct 循环、人设、梗库、画像、任务、技能、插件、QZone
│   ├── llm/           # 多供应商 ProviderManager
│   ├── onebot/        # OneBot 11 客户端 / 事件
│   ├── tools/         # 工具注册表（分级 + 渐进披露）
│   └── web.py         # 管理台后端 API
├── dashboard/         # Vue3 + Vuetify 管理台前端
├── tests/             # pytest 测试
└── Dockerfile / compose.yml
```

## License

MIT
