from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Appointment


@receiver(post_save, sender=Appointment)
def send_appointment_whatsapp_notification(sender, instance, created, **kwargs):
    """
    Post-save signal on Appointment model to automatically send a WhatsApp confirmation
    message to the patient whenever an Appointment instance is created in DB.
    """
    if created and instance.patient and instance.patient.contact_no:
        doctor_name = instance.doctor.get_full_name() if instance.doctor else "our specialist"
        formatted_date = instance.appointment_date.strftime("%b %d, %Y")
        formatted_time = instance.appointment_time.strftime("%I:%M %p")

        message_text = (
            f"Hello {instance.patient.get_full_name()},\n\n"
            f"Your appointment request at Sandhi Rheumatology Clinic has been CONFIRMED!\n\n"
            f"👨‍⚕️ Doctor: {doctor_name}\n"
            f"📅 Date: {formatted_date}\n"
            f"⏰ Time: {formatted_time}\n"
            f"🎟️ Token No: #{instance.token_number}\n\n"
            f"Please arrive 10 minutes prior to your slot."
        )

        try:
            from whatsapp.tasks import send_whatsapp_message
            send_whatsapp_message.delay(phone_number=instance.patient.contact_no, message=message_text)
        except Exception:
            try:
                from whatsapp.tasks import send_whatsapp_message
                send_whatsapp_message(phone_number=instance.patient.contact_no, message=message_text)
            except Exception:
                pass
