import re

from patient.models import PatientQueries, PatientProfile, PatientState
from .tasks import send_whatsapp_message
from django.utils import timezone


GREETING_RE = re.compile(r"^(hi+|hello+|hey+|hii+|hlo+|namaste|namaskar|good\s+(morning|afternoon|evening))\b", re.IGNORECASE)
SESSION_TIMEOUT_MINUTES = 15


def _is_greeting_message(message: str) -> bool:
    normalized = re.sub(r"[!.,?\-_/\\]+", " ", (message or "")).strip().lower()
    if not normalized:
        return False

    return bool(GREETING_RE.match(normalized)) and len(normalized.split()) <= 3


def _send_welcome_message(phone_number: str) -> None:
    send_whatsapp_message.delay(
        phone_number=phone_number,
        message=(
            "Thank you for contacting RheumaLink. Please share your query or concern, "
            "and we will assist you shortly."
        ),
    )


def _send_first_contact_prompt(phone_number: str) -> None:
    send_whatsapp_message.delay(
        phone_number=phone_number,
        message=(
            "Hello from RheumaLink. You have a 15-minute session. Please enter your "
            "concerns or query, and we will help you shortly."
        ),
    )


def _is_session_active(patient_state: PatientState) -> bool:
    if patient_state.state != "awaiting_query" or not patient_state.session_started_at:
        return False

    elapsed = timezone.now() - patient_state.session_started_at
    return elapsed.total_seconds() <= SESSION_TIMEOUT_MINUTES * 60


def dispatch_whatsapp_message(phone_number, message):
    user = PatientProfile.objects.filter(contact_no=phone_number).first()
    if not user:
        return {"ok": False, "error": f"No patient found with phone number {phone_number}"}

    patient_state, _ = PatientState.objects.get_or_create(patient=user)
    cleaned_message = (message or "").strip()
    if not cleaned_message:
        return {"ok": True, "ignored": True, "reason": "empty_message"}

    if patient_state.state == "awaiting_query" and not _is_session_active(patient_state):
        patient_state.state = "idle"
        patient_state.session_started_at = None
        patient_state.save(update_fields=["state", "session_started_at", "updated_at"])

    if patient_state.state == "idle":
        _send_first_contact_prompt(phone_number)
        patient_state.state = "awaiting_query"
        patient_state.session_started_at = timezone.now()
        patient_state.save(update_fields=["state", "session_started_at", "updated_at"])
        return {"ok": True, "ignored": True, "reason": "first_contact_prompt_sent"}

    if _is_greeting_message(cleaned_message):
        return {"ok": True, "ignored": True, "reason": "greeting_only"}
    
    # Log the incoming message for the patient
    PatientQueries.objects.create(
        patient=user,
        query=cleaned_message,
    )

    send_whatsapp_message.delay(
        phone_number=phone_number,
        message=(
            "Thank you for reaching out to RheumaLink. We have received your query "
            "and will get back to you shortly."
        ),
    )
    return {"ok": True, "message": "WhatsApp message dispatched successfully"}

    

    

    

    