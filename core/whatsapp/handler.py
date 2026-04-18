from patient.models import PatientQueries, PatientProfile
from .tasks import send_whatsapp_message


def dispatch_whatsapp_message(phone_number, message):
    user = PatientProfile.objects.filter(contact_no=phone_number).first()
    if not user:
        return {"ok": False, "error": f"No patient found with phone number {phone_number}"}
    
    # Log the incoming message for the patient
    PatientQueries.objects.create(
        patient=user,
        query=message,
    )

    send_whatsapp_message.delay(phone_number=phone_number, message="Thank you for reaching out to RheumaLink. We have received your message and will get back to you shortly.")
    return {"ok": True, "message": "WhatsApp message dispatched successfully"}

    

    

    

    