from datetime import date, datetime
import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages

from clinic.models import ClinicSettings
from doctor.models import Doctor
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

    # 1. Doctor Assignment: Directly assign specified doctor or fallback to first available doctor in DB
    assigned_doctor = None
    if doctor_id:
        try:
            assigned_doctor = Doctor.objects.filter(id=doctor_id).first()
        except (ValueError, TypeError):
            assigned_doctor = None

    if not assigned_doctor:
        assigned_doctor = Doctor.objects.first()

    # 2. Find or Create Patient Profile (Default Regular Mode)
    patient = None
    if phone:
        patient = PatientProfile.objects.filter(contact_no=phone).first()
    if not patient and email:
        patient = PatientProfile.objects.filter(email=email).first()

    if patient:
        # Update profile attributes if missing
        if first_name and not patient.first_name:
            patient.first_name = first_name
        if last_name and not patient.last_name:
            patient.last_name = last_name
        if email and not patient.email:
            patient.email = email
        if phone and not patient.contact_no:
            patient.contact_no = phone
        if dob and not patient.date_of_birth:
            try:
                patient.date_of_birth = datetime.strptime(dob, "%Y-%m-%d").date()
            except ValueError:
                pass
        if sex and sex in ['M', 'F', 'O'] and not patient.sex:
            patient.sex = sex
        patient.type = 'Regular'  # Force default regular mode
        patient.save()
    else:
        # Generate clean username
        clean_email = email.lower() if email else ""
        if clean_email:
            base_user = clean_email.split('@')[0]
        elif phone:
            base_user = f"patient_{phone.replace('+', '').replace(' ', '').replace('-', '')}"
        else:
            base_user = f"patient_{date.today().strftime('%Y%m%d%H%M%S')}"

        username = base_user
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_user}_{counter}"
            counter += 1

        dob_val = None
        if dob:
            try:
                dob_val = datetime.strptime(dob, "%Y-%m-%d").date()
            except ValueError:
                pass

        patient = PatientProfile.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            contact_no=phone,
            date_of_birth=dob_val,
            sex=sex if sex in ['M', 'F', 'O'] else '',
            type='Regular',  # Default regular mode
            role=User.Role.PATIENT
        )

    # Ensure patient has an active internal FileRecord
    file_record, _ = FileRecord.objects.get_or_create(patient=patient)

    # 3. Parse Appointment Date & Time
    appt_date = date.today()
    if appt_date_str:
        try:
            appt_date = datetime.strptime(appt_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    appt_time = datetime.now().time().replace(microsecond=0)
    if appt_time_str:
        try:
            appt_time = datetime.strptime(appt_time_str, "%H:%M").time()
        except ValueError:
            try:
                appt_time = datetime.strptime(appt_time_str, "%H:%M:%S").time()
            except ValueError:
                pass

    # 4. Create Appointment record
    appointment = Appointment.objects.create(
        patient=patient,
        doctor=assigned_doctor,
        appointment_date=appt_date,
        appointment_time=appt_time,
        reason_for_visit=combined_reason or "General Consultation",
        status='T'  # Status: To Be Attended
    )

    # Broadcast queue update for live dashboard synchronization
    if assigned_doctor:
        _broadcast_queue_update(assigned_doctor.id)
    else:
        _broadcast_queue_update()

    doctor_name = assigned_doctor.get_full_name() if assigned_doctor else "Assigned Doctor"

    if is_ajax:
        return JsonResponse({
            "status": "success",
            "message": "Appointment requested successfully!",
            "token_number": appointment.token_number,
            "file_number": file_record.internal_file_number,
            "doctor_name": doctor_name,
            "appointment_date": appointment.appointment_date.strftime("%b %d, %Y"),
            "appointment_time": appointment.appointment_time.strftime("%I:%M %p"),
            "patient_name": patient.get_full_name()
        })
    else:
        messages.success(request, f"Appointment booked! Your Token Number is #{appointment.token_number} with {doctor_name}.")
        return redirect("clinic-home")
