"""Status query endpoint.

Executes an already-classified `status_query` intent against GitHub using the
credentials configured in the server environment (.env). Returns a
WhatsApp-safe text fallback plus structured data for rich formatting.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from server.agents.status_agent import handle_status_query
from server.utils.credentials import github_token, github_owner, github_repo
from server.utils.logger import logger

router = APIRouter()


class StatusRequest(BaseModel):
    intent: dict
    # Optional per-request repo override; falls back to the server's env defaults.
    owner: Optional[str] = None
    repo: Optional[str] = None


_NO_REPO_MSG = (
    "No repository is connected yet.\n"
    "Set GITHUB_TOKEN (and optionally GITHUB_OWNER / GITHUB_REPO) in the server .env, "
    "then pick a repo with `!repo owner/name`. See your repos with `!repos`."
)


@router.post("/")
async def status(req: StatusRequest):
    token = github_token()
    owner = req.owner or github_owner()
    repo = req.repo or github_repo()

    if not token or not owner or not repo:
        return {"reply": _NO_REPO_MSG, "data": {"type": "empty", "message": _NO_REPO_MSG}}

    try:
        reply, data = await handle_status_query(req.intent, token, owner, repo)
        return {"reply": reply, "data": data}
    except Exception as e:
        logger.error(f"[status] error: {e}")
        return JSONResponse(
            status_code=500,
            content={"reply": f"Error: {e}", "data": {"type": "error", "message": str(e)}},
        )
