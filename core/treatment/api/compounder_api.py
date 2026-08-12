from datetime import date
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from patient.models import PatientProfile, FileRecord
from treatment.forms import PatientProfileForm, AppointmentForm
from treatment.models import Appointment
from treatment.serializers import PatientProfileSerializer, AppointmentSerializer
from treatment.views import _broadcast_queue_update

def _safe_str(val):
    if val is None:
        return ""
    return str(val).strip()

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_compounder_dashboard_api(request):
    """
    GET API for Compounder Dashboard using DRF Serializers.
    Returns today appointments, counts, and search results/recent patients.
    """
    try:
        search_q = request.GET.get("search_q") or request.GET.get("q")
        search_q = _safe_str(search_q)

        today_appts = Appointment.objects.select_related("patient__filerecord", "doctor").filter(
            appointment_date=date.today()
        ).order_by("appointment_time", "token_number", "id")
        
        waiting = len([a for a in today_appts if a.status not in ("I", "A")])
        attending = len([a for a in today_appts if a.status == "I"])
        attended = len([a for a in today_appts if a.status == "A"])
        total_today = len(today_appts)

        today_appts_data = AppointmentSerializer(today_appts, many=True).data

        recent_patients = []
        search_results = []
        is_recent_list = True

        if search_q:
            is_recent_list = False
            qs = PatientProfile.objects.select_related("filerecord").filter(
                first_name__icontains=search_q
            ) | PatientProfile.objects.select_related("filerecord").filter(
                last_name__icontains=search_q
            ) | PatientProfile.objects.select_related("filerecord").filter(
                contact_no__icontains=search_q
            ) | PatientProfile.objects.select_related("filerecord").filter(
                filerecord__external_file_number__icontains=search_q
            )
            search_results = PatientProfileSerializer(qs.distinct()[:20], many=True).data
        else:
            recent_qs = PatientProfile.objects.select_related("filerecord").order_by("-id")[:5]
            recent_patients = PatientProfileSerializer(recent_qs, many=True).data

        return Response({
            "ok": True,
            "counts": {
                "waiting": waiting,
                "attending": attending,
                "attended": attended,
                "total_today": total_today,
            },
            "today_appointments": today_appts_data,
            "recent_patients": recent_patients,
            "search_results": search_results,
            "is_recent_list": is_recent_list,
        })
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def register_patient_api(request):
    """
    POST API to register new patient profile utilizing PatientProfileSerializer.
    Validates external_file_number uniqueness and creates FileRecord directly.
    """
    try:
        data = request.data or {}
        raw_ext = data.get("external_file_number")
        ext_num = _safe_str(raw_ext) or None

        if ext_num and FileRecord.objects.filter(external_file_number=ext_num).exists():
            return Response({
                "ok": False,
                "errors": {
                    "external_file_number": [f"External file number '{ext_num}' is already assigned to another patient."]
                }
            }, status=400)

        form = PatientProfileForm(data)
        if form.is_valid():
            with transaction.atomic():
                patient = form.save()
                file_rec = FileRecord.objects.create(patient=patient, external_file_number=ext_num)

            serializer = PatientProfileSerializer(patient)
            return Response({
                "ok": True,
                "message": f"Patient '{patient.get_full_name()}' registered successfully.",
                "patient": serializer.data,
            })
        else:
            return Response({"ok": False, "errors": form.errors}, status=400)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_appointment_api(request):
    """
    POST API to create a new appointment utilizing AppointmentSerializer.
    Parses patient and doctor IDs safely from integer, string, or object.
    """
    try:
        data = request.data or {}
        patient_id = data.get("patient")
        doctor_id = data.get("doctor")

        payload = {
            "patient": patient_id,
            "doctor": doctor_id,
            "appointment_date": data.get("appointment_date") or date.today(),
            "appointment_time": data.get("appointment_time"),
            "status": data.get("status") or "T",
            "reason_for_visit": _safe_str(data.get("reason_for_visit")),
        }

        form = AppointmentForm(payload)
        if form.is_valid():
            appointment = form.save()
            _broadcast_queue_update(appointment.doctor_id)
            serializer = AppointmentSerializer(appointment)
            return Response({
                "ok": True,
                "message": f"Appointment created with token {appointment.token_number}.",
                "appointment": serializer.data,
            })
        else:
            return Response({"ok": False, "errors": form.errors}, status=400)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def update_appointment_status_api(request, appointment_id):
    """
    POST API to update an appointment's status or assigned doctor.
    """
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        data = request.data or {}

        status = data.get("status")
        doctor_id = data.get("doctor_id") or data.get("doctor")

        STATUS_MAP = {
            "to-be-attended": "T",
            "waiting": "T",
            "attending": "I",
            "in": "I",
            "attended": "A",
            "cancelled": "C",
            "no-show": "N",
            "absent": "N",
        }

        updated = False
        if status:
            new_status = STATUS_MAP.get(str(status).lower(), status)
            if new_status in dict(Appointment.STATUS_CHOICES):
                appointment.status = new_status
                updated = True

        if doctor_id:
            try:
                appointment.doctor_id = int(doctor_id)
                updated = True
            except (ValueError, TypeError):
                pass

        if updated:
            appointment.save()
            _broadcast_queue_update(appointment.doctor_id)

        serializer = AppointmentSerializer(appointment)
        return Response({
            "ok": True,
            "message": f"Appointment status updated to '{appointment.get_status_display()}'.",
            "appointment": serializer.data,
        })
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)
