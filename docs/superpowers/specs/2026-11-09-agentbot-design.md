# Agentbot 设计文档

日期：2026-11-09
状态：已确认（待实现）
项目目录：`/Users/a4869/project/ai-bot/lumina`

## 1. 背景与目标

现有 AstrBot（Python agentic 框架）接 SnowLuma（QQ 机器人运行时，OneBot 协议）跑在 Docker 里，但模型用的是本地 Ollama `qwen3:4b`，用户认为"不够智能"。

目标：新建一个 **纯 Python 的 lumina**，完全替换 AstrBot，通过 SnowLuma 暴露的约 193 个动作（OneBot v11 标准 + SnowLuma 原生扩展）做"根据接口智能执行"，用 DeepSeek 驱动，具备完全自治能力（多步 ReAct + 沙盒代码/Shell 执行），并对接 QQ（SnowLuma / NapCatQQ）。

## 2. 非目标（YAGNI）

- 不重做 QQ 客户端接入（复用 SnowLuma 的 OneBot）。
- 不做多租户 / SaaS、不做账号体系、不做 Web 管理后台（SnowLuma 已有 WebUI）。
- 不做消息平台抽象层（QQ 优先，其它平台以后再说）。
- 不在此版本引入 Dify/Coze 等外部编排。

## 3. 已确认的关键决策

| 决策点 | 结论 |
|---|---|
| 接口范围 | SnowLuma 全量动作：OneBot 11 标准 + 原生扩展（约 193 个） |
| 自治深度 | 完全自治：多步 ReAct 循环 + 沙盒代码/Shell 执行 |
| 接入机制 | 直连 OneBot（WS 收事件 + HTTP 调动作），非 MCP |
| 技术栈 | Python（FastAPI + openai SDK） |
| 模型 | 全用 `deepseek-flash`（V4.1-Flash，支持图文） |
| 安全 | 分级 allowlist（safe 放行 / risky 白名单 / forbidden 永不开放） |
| 与 AstrBot 关系 | 完全替换（停 AstrBot，SnowLuma 改指 lumina） |
| 定时任务 | APScheduler，任务可经 QQ 文本/语音 CRUD |
| 语音 | 走 SnowLuma `fetch_ptt_text` 转写，不接第三方 STT |
| 扩展性 | M2 多供应商 provider 抽象；M4 每用户个人知识库 |

## 4. 架构

```
QQ 用户 ──▶ SnowLuma (QQ NT + OneBot) ──WS事件──▶ lumina
                                                   │
                              ┌────────────────────┼────────────────────┐
                              │                    │                    │
                        OneBot 接入层          Agent 循环           工具层(193)
                        (websockets 收,        (ReAct + flash)      (自动生成 +
                        httpx 调 POST/{action})                      分级 allowlist)
                              │                    │                    │
                              └──────────┬─────────┴──────────┬─────────┘
                                         │                    │
                                    记忆/存储(SQLite)      沙盒(子进程)
```

## 5. 组件设计

### 5.1 OneBot 接入层
- 事件：`websockets` 正向客户端连 `ws://snowluma:3001/`（role Universal，accessToken 用 WS token）。
- 动作：`httpx` `POST http://snowluma:3000/{action}`，header `Authorization: Bearer <HTTP token>`。
- 处理事件类型：`message`（group / private，含 `record` 语音段）、`notice`、`request`（好友/群加请求）。

### 5.2 工具层
- 静态 schema 文件 `tools/snowluma_actions.json`：每个动作含 `name / category / description / params / risk_level`。
- 工厂根据 schema 生成 typed 可调用工具（pydantic 校验入参）。
- 风险分级：`safe`（发消息/只读查询）默认挂载；`risky`（踢人/禁言/删消息/群文件删除等）需白名单才挂载；`forbidden`（`bot_exit`/`set_restart`/取 cookies·凭据等）不生成。

### 5.3 Agent 循环
- ReAct 多步：收消息 → 拼上下文（系统提示 + 允许的工具清单 + 记忆）→ DeepSeek-flash function calling 选工具 → 执行 → 结果回喂 → 循环，直到模型返回最终回复。
- 护栏：最大步数（默认 8）、每轮成本/时间上限，防死循环。

### 5.4 沙盒执行
- 隔离子进程跑 Python 代码 / Shell：超时（默认 10s）、内存上限、默认无外网、独立工作目录。
- 沙盒与工具层隔离：沙盒内不直接暴露危险工具。

### 5.5 记忆 / 存储
- 单一 SQLite 文件（WAL）：会话历史（按 group/private + user 命名空间）、工具调用日志、定时任务、知识库（M4）。
- 会话历史按长度/轮次截断，长对话做压缩摘要。

### 5.6 多供应商抽象（M2，架构预留）
- `LLMProvider` 抽象 + `OpenAICompatProvider` 实现；provider 列表由配置驱动。
- M1 只实现 DeepSeek 一个 provider，但 Agent 循环只依赖抽象接口。

### 5.7 定时任务（M3）
- APScheduler 持久化任务；任务 CRUD 也暴露为工具（`create_task / list_tasks / update_task / delete_task`）。
- 语音指令：收到 `record` 段 → 调 `fetch_ptt_text` → 得到文本 → 走正常工具调用。

### 5.8 个人知识库（M4）
- 按 QQ 用户/群命名空间；嵌入用本地 Ollama `nomic-embed-text`；检索相似片段注入上下文。
- 每用户可增删查自己的文档。

## 6. 数据流（以"查群成员并 @ 某人"为例）

1. 群消息 → SnowLuma OneBot WS 事件 → lumina。
2. lumina 组装上下文（含工具清单 `get_group_member_list`、`send_group_msg` 等）。
3. DeepSeek 决定调 `get_group_member_list(group_id=...)` → lumina `POST /get_group_member_list` → 结果回喂。
4. DeepSeek 决定调 `send_group_msg(...)` → 执行 → 完成 → 最终回复。

## 7. 配置与环境变量

- `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）。
- `SNOWLUMA_HTTP_URL`（默认 `http://snowluma:3000/`）、`SNOWLUMA_WS_URL`（默认 `ws://snowluma:3001/`）、`SNOWLUMA_HTTP_TOKEN`、`SNOWLUMA_WS_TOKEN`。
- 密钥/token 全部走环境变量，不进代码库。

## 8. 部署

- 新建 Docker 容器 `lumina`，与 `snowluma` 同网络。
- 停掉并移除 AstrBot 容器；删除 SnowLuma 配置里 `wsClients["AstrBot"] → ws://astrbot:6199/ws` 条目，避免事件推到已停服务。

## 9. 测试

- 工具层：schema 解析、入参校验、风险分级单测。
- 集成：连 SnowLuma 收发消息、语音转写链路。
- 沙盒：超时、内存、越界（无外网）测试。
- Agent：工具选择、多步、护栏的 mock 测试。

## 10. 里程碑

- **M1**：核心 lumina（OneBot 直连 + 工具层 + ReAct + 记忆 + 沙盒 + 替换 AstrBot）。
- **M2**：多供应商 provider 抽象 + 统一配置。
- **M3**：定时任务 + 语音 CRUD。
- **M4**：个人知识库（RAG）。

## 11. 安全提醒

DeepSeek key 与 SnowLuma OneBot token 已在对话中明文出现，项目完成后建议全部轮换。
