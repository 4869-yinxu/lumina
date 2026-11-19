import pytest

from lumina.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_append_and_recent(tmp_path):
    m = MemoryStore(str(tmp_path / "mem.db"))
    await m.append("g:1", "user", "你好")
    await m.append("g:1", "assistant", "你好呀")
    recent = await m.recent("g:1")
    assert [x.content for x in recent] == ["你好", "你好呀"]


@pytest.mark.asyncio
async def test_scopes_isolated(tmp_path):
    m = MemoryStore(str(tmp_path / "mem.db"))
    await m.append("g:1", "user", "a")
    await m.append("u:2", "user", "b")
    assert len(await m.recent("g:1")) == 1
    assert len(await m.recent("u:2")) == 1


@pytest.mark.asyncio
async def test_clear(tmp_path):
    m = MemoryStore(str(tmp_path / "mem.db"))
    await m.append("g:1", "user", "a")
    await m.clear("g:1")
    assert await m.recent("g:1") == []
