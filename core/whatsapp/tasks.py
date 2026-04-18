import re
from logging import getLogger
from typing import Optional

import requests
from celery import shared_task # type: ignore

from .utils import extract_phone_number_from_user_id


logger = getLogger(__name__)

WHATSAPP_API_HOST = "http://whatsapp:3333"
WHATSAPP_SEND_TEXT_URL = f"{WHATSAPP_API_HOST}/sendText"



@shared_task(name="send_whatsapp_message_task", queue="primary")
def send_whatsapp_message(
    user_id: Optional[int] = None,
    phone_number: Optional[str] = None,
    message: str = "",
):
    """Send a plain text WhatsApp message through the wrapper service."""
    if not message or not message.strip():
        return {"ok": False, "error": "Message text is required"}

    resolved_phone_number = phone_number
    if not resolved_phone_number and user_id is not None:
        try:
            resolved_phone_number = extract_phone_number_from_user_id(user_id)
        except ValueError as exc:
            logger.error("Could not resolve phone number for user_id %s: %s", user_id, exc)
            return {"ok": False, "error": str(exc)}

    if not resolved_phone_number:
        return {"ok": False, "error": "Phone number is required to send WhatsApp message"}

    try:
        response = requests.post(
            WHATSAPP_SEND_TEXT_URL,
            json={"jid": f"91{resolved_phone_number}@s.whatsapp.net", "text": message},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Failed to send WhatsApp message to %s", f"91{resolved_phone_number}@s.whatsapp.net")
        return {"ok": False, "error": f"Failed to send WhatsApp message: {exc}"}

    logger.info("WhatsApp message sent successfully to %s", f"91{resolved_phone_number}@s.whatsapp.net")
    return {"ok": True, "jid": f"91{resolved_phone_number}@s.whatsapp.net", "status_code": response.status_code}
    

