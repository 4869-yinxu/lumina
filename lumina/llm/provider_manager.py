from __future__ import annotations

import os
import re

from lumina.llm.base import ChatMessage, ChatResponse, LLMProvider
from lumina.llm.openai_compat import OpenAICompatProvider

_ENV_RE = re.compile(r"^\$\{([A-Za-z0-9_]+)\}$")


def _resolve(value):
    if isinstance(value, str):
        m = _ENV_RE.match(value.strip())
        if m:
            return os.environ.get(m.group(1), "")
    return value


def load_providers_config(path: str) -> dict | None:
    if not path or not os.path.exists(path):
        return None
    import yaml

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_embedding_config(cfg: dict | None) -> tuple[str, str] | None:
    """从配置里找 type=embedding 的供应商，返回 (base_url, model)。"""
    for p in (cfg or {}).get("providers", []) or []:
        if p.get("type") == "embedding":
            return (_resolve(p.get("base_url", "")), _resolve(p.get("model", "")))
    return None


class ProviderManager(LLMProvider):
    def __init__(
        self,
        providers: dict[str, LLMProvider],
        default: str,
        fallback: list[str],
    ):
        self.providers = providers
        self.default = default
        self.fallback = fallback or []

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        max_tokens: int = 2048,
    ) -> ChatResponse:
        order: list[str] = []
        if self.default and self.default in self.providers:
            order.append(self.default)
        for pid in self.fallback:
            if pid in self.providers and pid not in order:
                order.append(pid)
        for pid in self.providers:
            if pid not in order:
                order.append(pid)

        last_err: Exception | None = None
        for pid in order:
            try:
                return await self.providers[pid].complete(messages, tools, max_tokens)
            except Exception as e:  # noqa: BLE001
                last_err = e
        if last_err is not None:
            raise last_err
        raise RuntimeError("no LLM provider available")

    @classmethod
    def from_config(
        cls,
        cfg: dict | None,
        env_defaults: dict | None = None,
    ) -> "ProviderManager":
        env_defaults = env_defaults or {}
        providers: dict[str, LLMProvider] = {}
        for p in (cfg or {}).get("providers", []) or []:
            pid = p.get("id")
            if not pid:
                continue
            if p.get("type") not in (None, "", "chat", "vision", "multimodal"):
                continue
            providers[pid] = OpenAICompatProvider(
                api_key=_resolve(p.get("api_key", "")),
                base_url=_resolve(p.get("base_url", "")),
                model=_resolve(p.get("model", "")),
            )
        if not providers:
            providers["deepseek"] = OpenAICompatProvider(
                api_key=env_defaults.get("api_key", ""),
                base_url=env_defaults.get("base_url", "https://api.deepseek.com"),
                model=env_defaults.get("model", "deepseek-flash"),
            )
        default = (cfg or {}).get("default_provider") or next(iter(providers))
        fallback = (cfg or {}).get("fallback") or []
        return cls(providers, default, fallback)
