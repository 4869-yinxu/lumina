from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict]
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class ChatResponse:
    message: ChatMessage
    finish_reason: str


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        max_tokens: int = 2048,
    ) -> ChatResponse:
        raise NotImplementedError
