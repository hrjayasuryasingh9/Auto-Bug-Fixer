import os
import httpx
from server.utils.logger import logger

_BASE = "https://graph.facebook.com/v19.0"


async def send_text(phone_number: str, text: str, phone_number_id: str | None = None, access_token: str | None = None) -> None:
    pid = phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    token = access_token or os.environ.get("WHATSAPP_ACCESS_TOKEN", "")

    if not pid or not token:
        logger.error("[whatsapp] Missing WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_ACCESS_TOKEN")
        return

    url = f"{_BASE}/{pid}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.error(f"[whatsapp] send failed {resp.status_code}: {resp.text[:200]}")
        else:
            logger.info(f"[whatsapp] sent to {phone_number}")


def parse_incoming(payload: dict) -> list[dict]:
    """Return list of {from, text, message_id} for each text message in a webhook payload."""
    messages = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    if msg.get("type") == "text":
                        messages.append({
                            "from": msg["from"],
                            "text": msg["text"]["body"],
                            "message_id": msg["id"],
                        })
    except Exception as e:
        logger.error(f"[whatsapp] parse error: {e}")
    return messages
