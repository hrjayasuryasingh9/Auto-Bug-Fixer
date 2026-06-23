from __future__ import annotations

import re
import subprocess
import asyncio
from typing import Optional
from server.utils.logger import logger

_TOKEN_RE = re.compile(r"(https?://)[\w\-]+:[^@]+@")


def _redact(cmd_str: str) -> str:
    """Replace token in HTTPS URLs so it never appears in logs."""
    return _TOKEN_RE.sub(r"\1***:***@", cmd_str)


async def run_cmd(args: list[str], cwd: str, env: Optional[dict] = None) -> str:
    """Run a command in a thread pool (Windows-safe, works on SelectorEventLoop)."""
    cmd_str = " ".join(args)
    safe_cmd = _redact(cmd_str)

    def _run():
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)

    result = await asyncio.to_thread(_run)

    if result.stdout.strip():
        logger.info(f"[{args[0]}] {result.stdout.strip()}")
    if result.stderr.strip():
        logger.info(f"[{args[0]} stderr] {result.stderr.strip()}")

    if result.returncode != 0:
        out = result.stdout.strip()
        err = result.stderr.strip()
        detail = "\n".join(filter(None, [out, err]))
        raise RuntimeError(f"'{safe_cmd}' failed (exit {result.returncode}):\n{detail}")

    return result.stdout


async def run_shell(cmd: str, cwd: str) -> bool:
    """Run a shell command. Returns True on success, False on failure (non-blocking)."""
    def _run():
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=True)

    result = await asyncio.to_thread(_run)

    if result.stdout.strip():
        logger.info(f"[{cmd}]\n{result.stdout.strip()}")
    if result.stderr.strip():
        logger.info(f"[{cmd} stderr]\n{result.stderr.strip()}")

    return result.returncode == 0
