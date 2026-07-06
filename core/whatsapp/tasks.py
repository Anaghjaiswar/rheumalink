import os
from logging import getLogger
from typing import Optional

import requests
from celery import shared_task # type: ignore
from django.core.files.storage import default_storage
from django.utils import timezone
from datetime import timedelta

from .utils import extract_phone_number_from_user_id
from patient.models import PatientState


logger = getLogger(__name__)

WHATSAPP_API_HOST = "http://whatsapp:3333"
WHATSAPP_SEND_TEXT_URL = f"{WHATSAPP_API_HOST}/sendText"
WHATSAPP_SEND_FILE_URL = f"{WHATSAPP_API_HOST}/sendFile"
SESSION_TIMEOUT_MINUTES = 15



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


@shared_task(name="send_whatsapp_file_task", queue="primary")
def send_whatsapp_file(
    file_path: str,
    file_name: Optional[str] = None,
    caption: str = "",
    user_id: Optional[int] = None,
    phone_number: Optional[str] = None,
    bucket_name: Optional[str] = None,
):
    """
    Send a file (image, PDF, etc.) with an optional caption to a patient's WhatsApp.
    The file can be a URL or a path relative to Django's storage.
    """
    if not file_path:
        return {"ok": False, "error": "file_path is required"}

    resolved_phone_number = phone_number
    if not resolved_phone_number and user_id is not None:
        try:
            resolved_phone_number = extract_phone_number_from_user_id(user_id)
        except ValueError as exc:
            logger.error("Could not resolve phone number for user_id %s: %s", user_id, exc)
            return {"ok": False, "error": str(exc)}

    if not resolved_phone_number:
        return {"ok": False, "error": "Phone number is required to send WhatsApp message"}

    # Resolve filename
    resolved_file_name = file_name or os.path.basename(file_path)

    # Get file content
    try:
        if file_path.startswith(("http://", "https://")):
            # Download remote file
            response = requests.get(file_path, timeout=30)
            response.raise_for_status()
            file_data = response.content
        else:
            # Read from Django storage (supports S3/MinIO/Local)
            if bucket_name:
                from storages.backends.s3 import S3Storage
                storage = S3Storage(bucket_name=bucket_name)
            else:
                storage = default_storage
            with storage.open(file_path, "rb") as f:
                file_data = f.read()
    except Exception as exc:
        logger.exception("Failed to retrieve file from %s", file_path)
        return {"ok": False, "error": f"Failed to retrieve file: {exc}"}

    # Send file request
    try:
        files = {
            "file": (resolved_file_name, file_data)
        }
        data = {
            "jid": f"91{resolved_phone_number}@s.whatsapp.net",
            "fileName": resolved_file_name,
            "caption": caption
        }
        response = requests.post(
            WHATSAPP_SEND_FILE_URL,
            files=files,
            data=data,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Failed to send file via WhatsApp to %s", f"91{resolved_phone_number}@s.whatsapp.net")
        return {"ok": False, "error": f"Failed to send file via WhatsApp: {exc}"}

    logger.info("WhatsApp file sent successfully to %s", f"91{resolved_phone_number}@s.whatsapp.net")
    return {"ok": True, "jid": f"91{resolved_phone_number}@s.whatsapp.net", "status_code": response.status_code}


@shared_task(name="cleanup_expired_whatsapp_sessions", queue="primary")
def cleanup_expired_whatsapp_sessions():
    cutoff = timezone.now() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    expired_sessions = PatientState.objects.filter(
        state="awaiting_query",
        session_started_at__lt=cutoff,
    )
    updated_count = expired_sessions.update(state="idle", session_started_at=None)
    logger.info("Reset %s expired WhatsApp sessions to idle", updated_count)
    return {"ok": True, "updated_count": updated_count}
    

