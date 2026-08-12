from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from clinic.models import ClinicSettings
from treatment.models import Prescription
from treatment.views import _generate_prescription_pdf
from whatsapp.tasks import send_whatsapp_file

def _get_user_role(request):
    if hasattr(request, 'auth') and isinstance(request.auth, dict) and 'role' in request.auth:
        return request.auth['role']
    return getattr(request.user, 'role', None)

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def download_prescription_pdf_api(request, prescription_id):
    """GET API to view/download prescription PDF with production grade exception handling."""
    try:
        prescription = get_object_or_404(Prescription, id=prescription_id)
        if not prescription.prescription_pdf:
            try:
                pdf_bytes = _generate_prescription_pdf(prescription)
                prescription.prescription_pdf.save(
                    f"rx_{prescription.consultation_id}.pdf",
                    ContentFile(pdf_bytes),
                    save=True,
                )
            except Exception as e:
                raise Http404(f"Prescription PDF generation failed: {e}")

        try:
            with prescription.prescription_pdf.open("rb") as f:
                response = HttpResponse(f.read(), content_type="application/pdf")
                response["Content-Disposition"] = f'inline; filename="prescription_{prescription_id}.pdf"'
                return response
        except Exception as e:
            raise Http404(f"Error reading PDF file: {e}")
    except Http404:
        raise
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def send_prescription_whatsapp_api(request, prescription_id):
    """POST API to dispatch WhatsApp prescription PDF via Celery task. Strict DOCTOR role required."""
    try:
        role = _get_user_role(request)
        if role != 'DOCTOR' and not getattr(request.user, 'is_superuser', False):
            return Response({"ok": False, "error": "Access denied. Doctor privileges required to dispatch prescriptions."}, status=403)

        prescription = get_object_or_404(Prescription, id=prescription_id)
        if not prescription.prescription_pdf:
            return Response({"ok": False, "error": "Prescription PDF has not been generated yet"}, status=400)

        patient = prescription.consultation.patient
        patient_phone = patient.contact_no

        if not patient_phone:
            return Response({"ok": False, "error": "Patient does not have a registered contact number"}, status=400)

        doctor_name = "your doctor"
        if prescription.consultation.appointment and prescription.consultation.appointment.doctor:
            doctor_name = prescription.consultation.appointment.doctor.get_full_name()

        clinic_name = "RheumaLink Clinic"
        clinic = ClinicSettings.objects.first()
        if clinic and clinic.name:
            clinic_name = clinic.name

        patient_name = patient.get_full_name()

        caption = (
            f"Intended for - {patient_name}\n\n"
            f"Here is the report of your today's consultation with {doctor_name}.\n\n"
            f"Stay healthy, stay happy!\n\n"
            f"Best regards,\n"
            f"{clinic_name}"
        )

        send_whatsapp_file.delay(
            file_path=prescription.prescription_pdf.name,
            file_name=f"prescription_{prescription.id}.pdf",
            caption=caption,
            phone_number=patient_phone,
            bucket_name=prescription.prescription_pdf.storage.bucket_name if hasattr(prescription.prescription_pdf.storage, 'bucket_name') else None
        )

        return Response({"ok": True, "message": "Prescription sending task dispatched successfully."})
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)
