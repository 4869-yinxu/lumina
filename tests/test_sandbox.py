import pytest

from lumina.sandbox.runner import run_python


@pytest.mark.asyncio
async def test_run_python_prints():
    r = await run_python("print(1+1)")
    assert r.stdout.strip() == "2"
    assert r.returncode == 0


@pytest.mark.asyncio
async def test_run_python_timeout():
    r = await run_python("import time; time.sleep(5)", timeout=0.2)
    assert r.timed_out is True


@pytest.mark.asyncio
async def test_run_python_error():
    r = await run_python("raise ValueError('x')")
    assert r.returncode != 0
    assert "ValueError" in r.stderr
