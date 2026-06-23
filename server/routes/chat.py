from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Any

from server.services.assistant import run_assistant
from server.utils.credentials import github_owner, github_repo
from server.utils.logger import logger

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = []
    technical: bool = False
    # Pre-classified intent — when provided, run_assistant skips re-parsing.
    intent: Optional[dict] = None
    # Optional per-request repo override; falls back to the server's env defaults.
    owner: Optional[str] = None
    repo: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None
    data: Optional[Any] = None
    cost_inr: Optional[float] = None
    graph_used: bool = False


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest):
    logger.info(f"[chat] {req.message[:80]}")
    try:
        owner = req.owner or github_owner()
        repo = req.repo or github_repo()
        result = await run_assistant(
            req.message, owner, repo,
            history=req.history or [], technical=req.technical, intent=req.intent,
        )
        return ChatResponse(**result)
    except Exception as e:
        logger.error(f"[chat] error: {e}")
        return JSONResponse(status_code=500, content={"reply": f"Error: {e}", "intent": "error", "data": None})
