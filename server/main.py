import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from server.routes.ai_fix import router as ai_fix_router
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
