"""Repo discovery + selection.

The GitHub token stays server-side (.env). Bridges use these endpoints to list
the repos that token can reach and to validate a repo the user wants to switch to.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server.adapters.github_adapter import list_user_repos, repo_exists
from server.utils.credentials import github_token, github_owner, github_repo
from server.utils.logger import logger

router = APIRouter()


@router.get("/")
async def list_repos():
    token = github_token()
    default = {"owner": github_owner(), "repo": github_repo()}
    if not token:
        return {
            "repos": [], "default": default, "has_token": False,
            "error": "No GITHUB_TOKEN configured on the server (.env).",
        }
    try:
        repos = await list_user_repos(token)
        return {"repos": repos, "default": default, "has_token": True}
    except Exception as e:
        logger.error(f"[repos] list failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"repos": [], "default": default, "has_token": True, "error": str(e)},
        )


@router.get("/check/{owner}/{repo}")
async def check_repo(owner: str, repo: str):
    token = github_token()
    if not token:
        return {"exists": False, "error": "No GITHUB_TOKEN configured on the server (.env)."}
    return {"exists": await repo_exists(owner, repo, token)}
