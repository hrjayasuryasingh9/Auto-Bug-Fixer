"""Issue / PR lifecycle actions — triggered by Slack interactive buttons.

These are the write counterparts to the read-only status queries:
  POST /api/actions/issue/close   → "Mark as fixed"  (close the issue)
  POST /api/actions/issue/delete  → "Delete issue"   (GraphQL deleteIssue)
  POST /api/actions/pr/merge      → "Merge with main" (merge the PR)
  POST /api/actions/pr/close      → "Delete PR"       (close PR + delete branch)

All are blocking (no SSE) — they finish in a single GitHub call or two, and the
bridge just updates the button message with the outcome.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.adapters.github_adapter import (
    close_issue, delete_issue, merge_pr, close_pr,
)
from server.utils.credentials import github_token
from server.utils.logger import logger

router = APIRouter()


class IssueAction(BaseModel):
    owner: str
    repo: str
    issue_number: int


class PRAction(BaseModel):
    owner: str
    repo: str
    pr_number: int


def _no_token():
    return JSONResponse(status_code=400, content={"success": False, "error": "No GitHub token configured"})


@router.post("/issue/close")
async def issue_close(req: IssueAction):
    token = github_token()
    if not token:
        return _no_token()
    logger.info(f"[actions] close issue {req.owner}/{req.repo}#{req.issue_number}")
    try:
        result = await close_issue(req.owner, req.repo, req.issue_number, token)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"[actions] close issue failed: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/issue/delete")
async def issue_delete(req: IssueAction):
    token = github_token()
    if not token:
        return _no_token()
    logger.info(f"[actions] delete issue {req.owner}/{req.repo}#{req.issue_number}")
    try:
        result = await delete_issue(req.owner, req.repo, req.issue_number, token)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"[actions] delete issue failed: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/pr/merge")
async def pr_merge(req: PRAction):
    token = github_token()
    if not token:
        return _no_token()
    logger.info(f"[actions] merge pr {req.owner}/{req.repo}#{req.pr_number}")
    try:
        result = await merge_pr(req.owner, req.repo, req.pr_number, token)
        # merge_pr returns merged=False (not an exception) when GitHub refuses.
        return {"success": result.get("merged", False), **result}
    except Exception as e:
        logger.error(f"[actions] merge pr failed: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/pr/close")
async def pr_close(req: PRAction):
    token = github_token()
    if not token:
        return _no_token()
    logger.info(f"[actions] close pr {req.owner}/{req.repo}#{req.pr_number}")
    try:
        result = await close_pr(req.owner, req.repo, req.pr_number, token)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"[actions] close pr failed: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
