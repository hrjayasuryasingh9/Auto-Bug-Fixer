from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from server.services.graph_service import build_graph, query_graph, graph_exists, get_graph_meta
from server.utils.logger import logger

router = APIRouter()


class BuildRequest(BaseModel):
    github_token: str
    owner: str
    repo: str
    anthropic_api_key: Optional[str] = None


class QueryRequest(BaseModel):
    github_token: str
    owner: str
    repo: str
    question: str


@router.post("/build")
async def build_graph_bg(req: BuildRequest, background_tasks: BackgroundTasks):
    """Kick off graph build in background — returns immediately."""
    logger.info(f"[graph] background build requested: {req.owner}/{req.repo}")
    background_tasks.add_task(build_graph, req.owner, req.repo, req.github_token)
    return {"status": "building", "message": f"Graph build started for {req.owner}/{req.repo}"}


@router.post("/build/sync")
async def build_graph_sync(req: BuildRequest):
    """Synchronous build — waits for completion (use for testing)."""
    result = await build_graph(req.owner, req.repo, req.github_token)
    return result


@router.get("/status/{owner}/{repo}")
async def graph_status(owner: str, repo: str):
    meta = get_graph_meta(owner, repo)
    if meta:
        return {"exists": True, **meta}
    return {"exists": False}


@router.post("/query")
async def query_graph_endpoint(req: QueryRequest):
    if not graph_exists(req.owner, req.repo):
        return {"context": "", "has_graph": False}
    context = query_graph(req.owner, req.repo, req.question)
    return {"context": context, "has_graph": True}
