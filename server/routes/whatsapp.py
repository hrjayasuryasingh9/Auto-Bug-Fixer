import hashlib
import hmac
import os
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse

from server.adapters.whatsapp_adapter import parse_incoming, send_text
from server.services.commands import handle_command
from server.services.context_store import resolve_repo, get_technical
from server.services.assistant import run_assistant
from server.utils.logger import logger

router = APIRouter()


@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("[whatsapp] Webhook verified by Meta")
        return hub_challenge or ""
    logger.warning("[whatsapp] Webhook verification failed")
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/webhooks/whatsapp")
async def receive_webhook(request: Request):
    body = await request.body()

    # Verify X-Hub-Signature-256
    app_secret = os.environ.get("WHATSAPP_APP_SECRET", "")
    if app_secret:
        sig_header = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            logger.warning("[whatsapp] Invalid signature — request rejected")
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        return {"status": "ok"}

    messages = parse_incoming(payload)
    for msg in messages:
        phone = msg["from"]
        text = msg["text"].strip()
        logger.info(f"[whatsapp] message from {phone}: {text[:80]}")
        await _handle_message(phone, text)

    return {"status": "ok"}


async def _handle_message(phone: str, text: str) -> None:
    """message -> commands / active-repo / intent + routing (all server-side)."""
    text = (text or "").strip()
    if not text:
        return

    # WhatsApp is 1:1 — phone identifies both the "channel" and the user.
    ctx = {"workspace_id": "whatsapp", "channel_id": phone, "thread_id": "", "user_id": phone}

    cmd_reply = await handle_command(text, ctx)
    if cmd_reply is not None:
        await send_text(phone, cmd_reply)
        return

    owner, repo = resolve_repo(ctx)
    technical = get_technical(ctx)
    result = await run_assistant(text, owner, repo, technical=technical, ctx=ctx)
    await send_text(phone, result["reply"])
