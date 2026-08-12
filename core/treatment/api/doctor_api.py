from datetime import date
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from doctor.models import Doctor
from treatment.forms import ConsultationForm, PrescriptionForm
from treatment.models import Appointment, Consultation, LabTest, Medicine, Prescription, PrescriptionItem
from treatment.serializers import (
    AppointmentSerializer,
    ConsultationSerializer,
    DoctorSerializer,
    LabTestSerializer,
    PrescriptionSerializer,
)
from treatment.views import _broadcast_queue_update

def _safe_str(val):
    if val is None:
        return ""
    return str(val).strip()

def _get_user_role(request):
    if hasattr(request, 'auth') and isinstance(request.auth, dict) and 'role' in request.auth:
        return request.auth['role']
    return getattr(request.user, 'role', None)

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_doctors_list_api(request):
    """
    GET API to return list of active clinic doctors.
    Accessible by staff accounts (COMPOUNDER or DOCTOR).
    """
    try:
        doctors_list = DoctorSerializer(Doctor.objects.all(), many=True).data
        return Response({"ok": True, "doctors": doctors_list})
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_doctor_dashboard_api(request):
    """
    GET API for Doctor Dashboard using DRF Serializers & Strict JWT Role Check.
    Filters appointments strictly by appointment_date = date.today().
    """
    try:
        role = _get_user_role(request)
        if role != 'DOCTOR' and not getattr(request.user, 'is_superuser', False):
            return Response({"ok": False, "error": "Access denied. Only doctors can access the Doctor Desk."}, status=403)

        doctor_id = request.GET.get("doctor_id") or request.GET.get("doctor")
        if doctor_id:
            try:
                doctor_id = int(doctor_id)
            except (ValueError, TypeError):
                doctor_id = None

        appointments = Appointment.objects.select_related("patient__filerecord", "doctor").filter(appointment_date=date.today())
        if doctor_id:
            appointments = appointments.filter(doctor_id=doctor_id)

        attending = AppointmentSerializer(appointments.filter(status="I"), many=True).data
        attended = AppointmentSerializer(appointments.filter(status="A"), many=True).data
        waiting = AppointmentSerializer(appointments.filter(status="T"), many=True).data

        doctors_list = DoctorSerializer(Doctor.objects.all(), many=True).data
        common_tests = LabTestSerializer(LabTest.objects.filter(is_common=True), many=True).data

        return Response({
            "ok": True,
            "attending": attending,
            "attended": attended,
            "waiting": waiting,
            "counts": {
                "waiting": len(waiting),
                "attending": len(attending),
                "attended": len(attended),
                "total_today": len(attending) + len(attended) + len(waiting),
            },
            "doctors": doctors_list,
            "common_tests": common_tests,
        })
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)

@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def save_consultation_api(request, appointment_id):
    """
    POST API to save doctor consultation and prescription.
    Requires Strict DOCTOR JWT role check.
    Uses multi-table atomic transactions for integrity.
    """
    try:
        role = _get_user_role(request)
        if role != 'DOCTOR' and not getattr(request.user, 'is_superuser', False):
            return Response({"ok": False, "error": "Access denied. Only doctors can save consultations."}, status=403)

        appointment = get_object_or_404(Appointment, id=appointment_id)
        data = request.data.copy()

        consult_form = ConsultationForm({
            "chief_complaints": _safe_str(data.get("chief_complaints")),
            "clinical_findings": _safe_str(data.get("clinical_findings")),
            "diagnosis": _safe_str(data.get("diagnosis")),
        })

        prescription_form = PrescriptionForm({
            "doctor": appointment.doctor_id,
            "patient": appointment.patient_id,
        })

        if consult_form.is_valid() and prescription_form.is_valid():
            with transaction.atomic():
                consultation, _ = Consultation.objects.update_or_create(
                    appointment=appointment,
                    defaults=consult_form.cleaned_data
                )

                prescription, _ = Prescription.objects.update_or_create(
                    appointment=appointment,
                    defaults={
                        "doctor": appointment.doctor,
                        "patient": appointment.patient,
                        "consultation": consultation
                    }
                )

                prescribed_tests = data.get("prescribed_tests", [])
                if isinstance(prescribed_tests, list) and prescribed_tests:
                    valid_tests = LabTest.objects.filter(id__in=prescribed_tests)
                    prescription.prescribed_tests.set(valid_tests)

                items = data.get("items", [])
                if isinstance(items, list) and items:
                    prescription.items.all().delete()
                    for item in items:
                        med_name = _safe_str(item.get("medicine"))
                        if not med_name:
                            continue
                        medicine, _ = Medicine.objects.get_or_create(name=med_name)
                        PrescriptionItem.objects.create(
                            prescription=prescription,
                            medicine=medicine,
                            dosage=_safe_str(item.get("dosage")),
                            duration=_safe_str(item.get("duration")),
                            instructions=_safe_str(item.get("instructions")),
                        )

                post_status = _safe_str(data.get("post_consult_status"))
                if post_status in ["A", "I"]:
                    appointment.status = post_status
                    appointment.save(update_fields=["status", "updated_at"])

            _broadcast_queue_update(appointment.doctor_id)
            consult_data = ConsultationSerializer(consultation).data
            return Response({
                "ok": True,
                "message": "Consultation and prescription saved successfully.",
                "prescription_id": prescription.id,
                "consultation_id": consultation.id,
                "consultation": consult_data,
            })
        else:
            errors = {}
            if not consult_form.is_valid():
                errors["consultation"] = consult_form.errors
            if not prescription_form.is_valid():
                errors["prescription"] = prescription_form.errors
            return Response({"ok": False, "errors": errors}, status=400)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)
