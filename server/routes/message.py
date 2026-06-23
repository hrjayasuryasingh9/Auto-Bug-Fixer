"""Unified message endpoint — the single entry point for chat bridges.

The bridge stays dumb: it POSTs the structured context (workspace/channel/thread/
user) + message + history. All decisions (commands, active-repo selection, intent,
routing) happen here, scoped per-user via context_store.
"""
import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Any

from server.services.commands import handle_command
from server.services.context_store import resolve_repo, get_technical
from server.services.assistant import run_assistant
from server.utils.logger import logger

router = APIRouter()


class MessageRequest(BaseModel):
    message: str
    history: Optional[list] = []
    technical: bool = False
    # Structured multi-tenant context (Slack: workspace=team, channel, thread_ts, user)
    workspace_id: Optional[str] = ""
    channel_id: Optional[str] = ""
    thread_id: Optional[str] = ""
    user_id: Optional[str] = ""
    # Legacy flat key (e.g. WhatsApp phone). If given, used as channel+user.
    session_id: Optional[str] = None


class MessageResponse(BaseModel):
    reply: str
    intent: Optional[str] = None
    data: Optional[Any] = None
    cost_inr: Optional[float] = None
    graph_used: bool = False


def _build_ctx(req: "MessageRequest") -> dict:
    ws = req.workspace_id or ""
    ch = req.channel_id or req.session_id or ""
    th = req.thread_id or ""
    us = req.user_id or req.session_id or ""
    return {"workspace_id": ws, "channel_id": ch, "thread_id": th, "user_id": us}


@router.post("/", response_model=MessageResponse)
async def handle(req: MessageRequest):
    text = (req.message or "").strip()
    if not text:
        return MessageResponse(reply="")

    ctx = _build_ctx(req)
    logger.info(f"[message] {ctx['channel_id']}/{ctx['user_id']}: {text[:80]}")
    try:
        # 1️⃣  Explicit ! commands (repo selection, mode, help, status…)
        cmd_reply = await handle_command(text, ctx)
        if cmd_reply is not None:
            return MessageResponse(reply=cmd_reply, intent="command")

        # 2️⃣  Normal flow — resolve this user's active repo + answer style, then route
        owner, repo = resolve_repo(ctx)
        technical = req.technical or get_technical(ctx)
        result = await run_assistant(
            text, owner, repo, history=req.history or [], technical=technical, ctx=ctx
        )
        return MessageResponse(**result)
    except Exception as e:
        logger.error(f"[message] error: {e}")
        return JSONResponse(status_code=500, content={"reply": f"Error: {e}", "intent": "error", "data": None})


@router.post("/stream")
async def handle_stream(req: MessageRequest):
    """Same as POST / but streams real progress events (SSE) for a live loader,
    ending with {stage:"done", result:{...}}."""
    text = (req.message or "").strip()
    ctx = _build_ctx(req)
    logger.info(f"[message:stream] {ctx['channel_id']}/{ctx['user_id']}: {text[:80]}")
    queue: asyncio.Queue = asyncio.Queue()

    async def progress(ev: dict) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            if not text:
                result = {"reply": "", "intent": None, "data": None, "cost_inr": None, "graph_used": False}
            else:
                cmd_reply = await handle_command(text, ctx)
                if cmd_reply is not None:
                    result = {"reply": cmd_reply, "intent": "command", "data": None, "cost_inr": None, "graph_used": False}
                else:
                    owner, repo = resolve_repo(ctx)
                    technical = req.technical or get_technical(ctx)
                    result = await run_assistant(
                        text, owner, repo, history=req.history or [],
                        technical=technical, ctx=ctx, progress=progress,
                    )
            await queue.put({"stage": "done", "result": result})
        except Exception as e:
            logger.error(f"[message:stream] error: {e}")
            await queue.put({"stage": "done", "result": {"reply": f"Error: {e}", "intent": "error", "data": None}})
        finally:
            await queue.put(None)

    async def gen():
        task = asyncio.create_task(runner())
        try:
            while True:
                ev = await queue.get()
                if ev is None:
                    break
                yield f"data: {json.dumps(ev)}\n\n"
        finally:
            await task

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
