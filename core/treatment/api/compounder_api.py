from datetime import date
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from patient.models import FileRecord, PatientProfile
from treatment.forms import AppointmentForm, PatientProfileForm
from treatment.models import Appointment
from treatment.views import _broadcast_queue_update

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_compounder_dashboard_api(request):
    """
    GET API for Compounder Dashboard overview.
    Requires JWT or Session authentication.
    """
    search_q = request.GET.get("search_q", "").strip()
    is_recent_list = False
    if search_q:
        search_results_qs = PatientProfile.objects.select_related("filerecord").filter(
            Q(first_name__icontains=search_q) |
            Q(last_name__icontains=search_q) |
            Q(contact_no__icontains=search_q) |
            Q(filerecord__internal_file_number__icontains=search_q) |
            Q(filerecord__external_file_number__icontains=search_q)
        ).distinct()[:15]
    else:
        search_results_qs = PatientProfile.objects.select_related("filerecord").order_by("-id")[:10]
        is_recent_list = True

    search_results = []
    for p in search_results_qs:
        search_results.append({
            "id": p.id,
            "name": p.get_full_name(),
            "contact": p.contact_no,
            "internal_file": p.filerecord.internal_file_number if hasattr(p, "filerecord") else "-",
            "external_file": p.filerecord.external_file_number if (hasattr(p, "filerecord") and p.filerecord.external_file_number) else "-",
            "type": p.type,
        })

    today_appts = Appointment.objects.select_related("patient__filerecord", "doctor").filter(appointment_date=date.today())
    
    appts_data = []
    waiting_count = 0
    attending_count = 0
    attended_count = 0

    for appt in today_appts:
        if appt.status == "T":
            waiting_count += 1
        elif appt.status == "I":
            attending_count += 1
        elif appt.status == "A":
            attended_count += 1

        appts_data.append({
            "id": appt.id,
            "token": f"Token {appt.token_number}",
            "token_number": appt.token_number,
            "patient_id": appt.patient_id,
            "patient_name": appt.patient.get_full_name(),
            "file": appt.patient.filerecord.internal_file_number if hasattr(appt.patient, "filerecord") else "-",
            "doctor": appt.doctor.get_full_name() if appt.doctor else "Unassigned",
            "status": appt.get_status_display(),
            "status_code": appt.status,
            "visit_reason": appt.reason_for_visit or "",
        })

    recent_patients = []
    for p in PatientProfile.objects.select_related("filerecord").order_by("-id")[:10]:
        recent_patients.append({
            "id": p.id,
            "name": p.get_full_name(),
            "contact": p.contact_no,
            "internal_file": p.filerecord.internal_file_number if hasattr(p, "filerecord") else "-",
            "type": p.type,
        })

    return Response({
        "ok": True,
        "counts": {
            "waiting": waiting_count,
            "attending": attending_count,
            "attended": attended_count,
            "total_today": today_appts.count(),
        },
        "today_appointments": appts_data,
        "recent_patients": recent_patients,
        "search_results": search_results,
        "is_recent_list": is_recent_list,
    })


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def register_patient_api(request):
    """
    POST API to register new patient profile.
    Requires JWT or Session authentication.
    """
    data = request.data
    form = PatientProfileForm(data)
    if form.is_valid():
        patient = form.save()
        ext_num = data.get("external_file_number", "").strip() or None
        file_rec, created = FileRecord.objects.get_or_create(patient=patient, defaults={"external_file_number": ext_num})
        if not created and ext_num and not file_rec.external_file_number:
            file_rec.external_file_number = ext_num
            file_rec.save()

        return Response({
            "ok": True,
            "message": f"Patient '{patient.get_full_name()}' registered successfully.",
            "patient": {
                "id": patient.id,
                "name": patient.get_full_name(),
                "internal_file": file_rec.internal_file_number,
                "external_file": file_rec.external_file_number or "-",
                "contact": patient.contact_no,
            }
        })
    else:
        return Response({"ok": False, "errors": form.errors}, status=400)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_appointment_api(request):
    """
    POST API to create a new appointment.
    Requires JWT or Session authentication.
    """
    data = request.data
    form = AppointmentForm(data)
    if form.is_valid():
        appointment = form.save()
        _broadcast_queue_update(appointment.doctor_id)
        return Response({
            "ok": True,
            "message": f"Appointment created with token {appointment.token_number}.",
            "appointment": {
                "id": appointment.id,
                "token_number": appointment.token_number,
                "patient_id": appointment.patient_id,
                "doctor_id": appointment.doctor_id,
                "date": appointment.appointment_date.strftime("%Y-%m-%d"),
            }
        })
    else:
        return Response({"ok": False, "errors": form.errors}, status=400)
