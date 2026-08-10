from datetime import date
import json
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from patient.models import FileRecord, PatientMedicalInfo, PatientProfile
from treatment.forms import AppointmentForm, AppointmentUpdateForm, PatientProfileForm
from treatment.models import Appointment, LabResult
from treatment.views import _broadcast_queue_update

@csrf_exempt
def get_compounder_dashboard_api(request):
    """
    GET API for Compounder Dashboard overview.
    Returns today's appointments (waiting, attending, attended), search results if query provided,
    recent patients, and pending lab reports.
    """
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Only GET allowed"}, status=405)

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

    return JsonResponse({
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


@csrf_exempt
def register_patient_api(request):
    """POST API to register new patient profile."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
        form = PatientProfileForm(data)
        if form.is_valid():
            patient = form.save()
            ext_num = data.get("external_file_number", "").strip() or None
            file_rec, created = FileRecord.objects.get_or_create(patient=patient, defaults={"external_file_number": ext_num})
            if not created and ext_num and not file_rec.external_file_number:
                file_rec.external_file_number = ext_num
                file_rec.save()

            return JsonResponse({
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
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@csrf_exempt
def create_appointment_api(request):
    """POST API to create a new appointment."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
        form = AppointmentForm(data)
        if form.is_valid():
            appointment = form.save()
            _broadcast_queue_update(appointment.doctor_id)
            return JsonResponse({
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
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
