import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from server.routes.ai_fix import router as ai_fix_router
from server.routes.whatsapp import router as whatsapp_router
from server.routes.chat import router as chat_router
from server.routes.graph import router as graph_router
from server.routes.intent import router as intent_router
from server.routes.status import router as status_router
from server.routes.repos import router as repos_router
from server.routes.message import router as message_router
from server.routes.fix_issue import router as fix_issue_router
from server.utils.logger import logger, LOG_FILE

load_dotenv()

app = FastAPI(title="AI Error Fixer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_fix_router, prefix="/api/ai-fix")
app.include_router(whatsapp_router)
app.include_router(chat_router, prefix="/api/chat")
app.include_router(graph_router, prefix="/api/graph")
app.include_router(intent_router, prefix="/api/intent")
app.include_router(status_router, prefix="/api/status")
app.include_router(repos_router, prefix="/api/repos")
app.include_router(message_router, prefix="/api/message")
app.include_router(fix_issue_router, prefix="/api/fix-issue")

_STATIC = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_STATIC):
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")

    @app.get("/")
    async def serve_ui():
        return FileResponse(os.path.join(_STATIC, "index.html"))


@app.on_event("startup")
async def startup():
    logger.info("=" * 60)
    logger.info("AI Error Fixer server started")
    logger.info(f"Logs -> {os.path.abspath(LOG_FILE)}")
    logger.info("=" * 60)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"[http] {request.method} {request.url.path} — from {request.client.host}")
    response = await call_next(request)
    logger.info(f"[http] {request.method} {request.url.path} — {response.status_code}")
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}
