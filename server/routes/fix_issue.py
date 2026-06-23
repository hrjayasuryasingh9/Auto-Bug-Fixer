"""Issue → PR endpoint. Triggered by the Slack "Fix this issue" button / command.

`POST /api/fix-issue/`        → runs and returns the final result (blocking).
`POST /api/fix-issue/stream`  → Server-Sent Events: streams REAL progress events
                                (clone → graph → analyze → plan → write → pr) and
                                a final {stage:"done", result:{...}} event. The Slack
                                bridge renders these as a live checklist.
"""
import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from server.services.fix_issue import fix_issue
from server.utils.logger import logger

router = APIRouter()


class FixIssueRequest(BaseModel):
    owner: str
    repo: str
    issue_number: int


@router.post("/")
async def handle_fix_issue(req: FixIssueRequest):
    logger.info(f"[fix-issue] request: {req.owner}/{req.repo}#{req.issue_number}")
    try:
        result = await fix_issue(req.owner, req.repo, req.issue_number)
        return result
    except Exception as e:
        logger.error(f"[fix-issue] failed: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/stream")
async def stream_fix_issue(req: FixIssueRequest):
    logger.info(f"[fix-issue] stream: {req.owner}/{req.repo}#{req.issue_number}")
    queue: asyncio.Queue = asyncio.Queue()

    async def progress(ev: dict) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            result = await fix_issue(req.owner, req.repo, req.issue_number, progress=progress)
            await queue.put({"stage": "done", "result": result})
        except Exception as e:
            logger.error(f"[fix-issue] stream failed: {e}")
            await queue.put({"stage": "done", "result": {"success": False, "error": str(e)}})
        finally:
            await queue.put(None)  # sentinel → end of stream

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
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
