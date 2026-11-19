# 部署说明

采用与 AstrBot 相同的接入模式：

- **事件**：SnowLuma 作为 WS 客户端（反向 WebSocket）连到 lumina，推送 QQ 消息事件。
- **动作**：lumina 通过 SnowLuma 的 OneBot HTTP API（`POST http://snowluma:3000/{action}`，`Authorization: Bearer <token>`）调用。

> 注意：SnowLuma 的反向 WS 只用于事件推送，不回传 action 响应；动作必须走 HTTP :3000。

1. 确认 `snowluma` 容器在运行，且与 lumina 同处一个 docker 网络（复用 `astrbot_botnet`）。
2. 复制环境变量：`cp .env.example .env` 并填入：
   - `LUMINA_DEEPSEEK_API_KEY`：DeepSeek key。
   - `LUMINA_SNOWLUMA_HTTP_TOKEN`：SnowLuma OneBot HTTP 的 access token（在 `onebot_3837425549.json` 的 `httpServers[].accessToken`）。
3. 停掉旧 AstrBot：`docker stop astrbot && docker rm astrbot`。
4. 修改 SnowLuma 的 OneBot 配置（`onebot_3837425549.json` 的 `networks.wsClients`）：
   把 `name == "AstrBot"` 那条的 `url` 改成 `ws://lumina:8080/ws`。
5. 启动 lumina：`docker compose up -d --build`。
6. 重启 SnowLuma 使其加载新配置（QQ 登录态会保留，一般无需重新扫码）。
7. 验证：`docker logs -f lumina`；在 QQ 群发消息看是否回复。
