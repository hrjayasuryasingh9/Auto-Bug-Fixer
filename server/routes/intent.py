"""Intent classification endpoint.

The single source of truth for "what does this message want". The WhatsApp
bridge no longer guesses intent with regexes — it POSTs the raw message here
and routes on the AI-classified result.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from server.agents.intent_parser import parse_intent
from server.utils.credentials import openai_key
from server.utils.logger import logger

router = APIRouter()


class IntentRequest(BaseModel):
    message: str
    history: Optional[list] = []


@router.post("/")
async def classify_intent(req: IntentRequest):
    logger.info(f"[intent] classify: {req.message[:80]}")
    try:
        intent = await parse_intent(
            req.message,
            api_key=openai_key(),
            history=req.history or [],
        )
        return intent
    except Exception as e:
        logger.error(f"[intent] error: {e}")
        return JSONResponse(
            status_code=500,
            content={"intent": "unknown", "confidence": 0.0, "entities": {}, "summary": str(e)},
        )
