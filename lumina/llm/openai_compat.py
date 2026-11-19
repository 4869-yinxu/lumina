from __future__ import annotations

import json

from openai import AsyncOpenAI

from lumina.llm.base import ChatMessage, ChatResponse, LLMProvider, ToolCall


class OpenAICompatProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str, model: str):
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def _to_openai(self, m: ChatMessage) -> dict:
        msg: dict = {"role": m.role, "content": m.content}
        if m.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in m.tool_calls
            ]
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        return msg

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        max_tokens: int = 2048,
    ) -> ChatResponse:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[self._to_openai(m) for m in messages],
            tools=tools or None,
            max_tokens=max_tokens,
        )
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in (msg.tool_calls or [])
        ]
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=msg.content or "",
                tool_calls=tool_calls,
            ),
            finish_reason=choice.finish_reason or "",
        )
