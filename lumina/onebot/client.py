from __future__ import annotations

import asyncio
import json

import httpx
import websockets


class OneBotClient:
    def __init__(
        self,
        http_url: str,
        ws_url: str,
        http_token: str = "",
        ws_token: str = "",
        reverse_host: str = "0.0.0.0",
        reverse_port: int = 8080,
    ):
        self.http_url = http_url.rstrip("/")
        self.ws_url = ws_url
        self.http_token = http_token
        self.ws_token = ws_token
        self.reverse_host = reverse_host
        self.reverse_port = reverse_port
        self._http = httpx.AsyncClient(base_url=self.http_url, timeout=30.0)
        self._on_event = None

    def _headers(self) -> dict:
        if self.http_token:
            return {"Authorization": f"Bearer {self.http_token}"}
        return {}

    async def call_action(self, action: str, params: dict) -> dict:
        resp = await self._http.post(f"/{action}", json=params, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "ok":
            raise RuntimeError(f"onebot action {action} failed: {data}")
        return data.get("data", data)

    async def serve_ws(self, on_event, host: str | None = None, port: int | None = None) -> None:
        self._on_event = on_event
        host = host or self.reverse_host
        port = port or self.reverse_port

        async def handler(ws):
            try:
                async for raw in ws:
                    data = json.loads(raw)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("post_type") and self._on_event:
                            result = self._on_event(item)
                            if asyncio.iscoroutine(result):
                                await result
            except websockets.ConnectionClosed:
                pass

        async with websockets.serve(handler, host, port):
            await asyncio.Future()

    async def connect_ws(self, on_event) -> None:
        headers = {}
        if self.ws_token:
            headers["Authorization"] = f"Bearer {self.ws_token}"
        async for ws in websockets.connect(self.ws_url, additional_headers=headers):
            try:
                async for raw in ws:
                    event = json.loads(raw)
                    if event.get("post_type") == "message":
                        on_event(event)
            except websockets.ConnectionClosed:
                continue

    async def aclose(self) -> None:
        await self._http.aclose()
