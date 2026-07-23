from datetime import date, datetime
import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages

from clinic.models import ClinicSettings
from doctor.models import Doctor
from notification.models import Notification
from patient.models import PatientProfile, FileRecord
from treatment.models import Appointment
from treatment.views import _broadcast_queue_update
from user.models import User


def clinic_home(request):
    """
    Renders the Clinic Home Page inspired by sandhi-rheumatology-clinic-india.html,
    populated with ClinicSettings and Doctor models.
    Also handles form POST for appointment booking.
    """
    if request.method == "POST":
        return _handle_appointment_booking(request)

    clinic = ClinicSettings.objects.select_related('address').first()
    doctors = Doctor.objects.all()
    primary_doctor = doctors.first()

    context = {
        "clinic": clinic,
        "doctors": doctors,
        "primary_doctor": primary_doctor,
        "today_date": date.today().strftime("%Y-%m-%d"),
    }
    return render(request, "clinic/home.html", context)


@csrf_exempt
@require_POST
def book_appointment_api(request):
    """
    API endpoint for booking a clinic appointment/visit.
    Directly assigns the doctor and sets patient mode to Regular by default.
    """
    
    return _handle_appointment_booking(request)


def _handle_appointment_booking(request):
    is_json = request.content_type == "application/json"
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or is_json or "application/json" in request.META.get("HTTP_ACCEPT", "")

    if is_json:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}
    else:
        data = request.POST

    # Extract patient fields
    full_name = data.get("name", "").strip()
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()

    if full_name and not (first_name or last_name):
        parts = full_name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip() or data.get("contact_no", "").strip()
    dob = data.get("date_of_birth", "").strip() or data.get("dob", "").strip()
    sex = data.get("sex", "").strip()

    # Extract appointment visit fields
    doctor_id = data.get("doctor_id") or data.get("doctor")
    appt_date_str = data.get("date", "").strip() or data.get("appointment_date", "").strip()
    appt_time_str = data.get("time", "").strip() or data.get("appointment_time", "").strip()
    reason = data.get("reason", "").strip() or data.get("reason_for_visit", "").strip()
    notes = data.get("notes", "").strip()

    combined_reason = reason
    if notes:
        combined_reason = f"{reason} - {notes}" if reason else notes

    # Validate mandatory patient identification
    if not first_name:
        err_msg = "Please provide your full name."
        if is_ajax:
            return JsonResponse({"status": "error", "message": err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect("clinic-home")

    if not phone and not email:
        err_msg = "Please provide at least a contact phone number or email address."
        if is_ajax:
            return JsonResponse({"status": "error", "message": err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect("clinic-home")

    # 1. Doctor Assignment: Resolve doctor for request routing
    assigned_doctor = None
    if doctor_id:
        try:
            assigned_doctor = Doctor.objects.filter(id=doctor_id).first()
        except (ValueError, TypeError):
            assigned_doctor = None

    if not assigned_doctor:
        assigned_doctor = Doctor.objects.first()

    doctor_name = assigned_doctor.get_full_name() if assigned_doctor else "Assigned Doctor"
    full_patient_name = f"{first_name} {last_name}".strip()

    # 2. Create Notification for Compounder Desk (No Patient or Appointment DB rows created yet)
    Notification.objects.create(
        target_role=Notification.TargetRole.COMPOUNDER,
        notification_type=Notification.NotificationType.APPOINTMENT,
        priority=Notification.Priority.HIGH,
        title=f"New Appointment Request: {full_patient_name}",
        message_json={
            "type": "APPOINTMENT_REQUEST",
            "name": full_patient_name,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "email": email,
            "doctor_id": assigned_doctor.id if assigned_doctor else None,
            "doctor_name": doctor_name,
            "appointment_date": appt_date_str or date.today().strftime("%Y-%m-%d"),
            "appointment_time": appt_time_str or "09:00",
            "sex": sex,
            "dob": dob,
            "reason": reason,
            "notes": notes,
            "status": "PENDING"
        }
    )

    if is_ajax:
        return JsonResponse({
            "status": "success",
            "message": "We have received your request. You will get an update from us shortly."
        })
    else:
        messages.success(request, "We have received your request. You will get an update from us shortly.")
        return redirect("clinic-home")
