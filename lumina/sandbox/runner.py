from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False


async def run_python(code: str, timeout: float = 10.0) -> SandboxResult:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        code,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return SandboxResult(
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            returncode=proc.returncode if proc.returncode is not None else -1,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return SandboxResult(
            stdout="", stderr="timed out", returncode=-1, timed_out=True
        )
