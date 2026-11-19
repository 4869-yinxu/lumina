import pytest

from lumina.llm.base import ChatMessage, ChatResponse, LLMProvider
from lumina.llm.provider_manager import ProviderManager


class FailingProvider(LLMProvider):
    async def complete(self, messages, tools, max_tokens=2048):
        raise RuntimeError("boom")


class OkProvider(LLMProvider):
    def __init__(self, tag):
        self.tag = tag

    async def complete(self, messages, tools, max_tokens=2048):
        return ChatResponse(ChatMessage("assistant", f"from {self.tag}"), "stop")


@pytest.mark.asyncio
async def test_fallback_on_failure():
    m = ProviderManager({"a": FailingProvider(), "b": OkProvider("b")}, "a", ["b"])
    r = await m.complete([ChatMessage("user", "hi")], [])
    assert r.message.content == "from b"


@pytest.mark.asyncio
async def test_default_used_first():
    m = ProviderManager({"a": OkProvider("a"), "b": OkProvider("b")}, "a", ["b"])
    r = await m.complete([], [])
    assert r.message.content == "from a"


def test_from_config_builds_providers():
    cfg = {
        "providers": [{"id": "p1", "base_url": "http://x", "api_key": "k", "model": "m"}],
        "default_provider": "p1",
        "fallback": [],
    }
    m = ProviderManager.from_config(cfg, env_defaults={"api_key": "dk", "base_url": "d", "model": "dm"})
    assert "p1" in m.providers
    assert m.default == "p1"


def test_from_config_empty_falls_back_to_env():
    m = ProviderManager.from_config(
        None, env_defaults={"api_key": "dk", "base_url": "http://d", "model": "dm"}
    )
    assert "deepseek" in m.providers
    assert m.default == "deepseek"
