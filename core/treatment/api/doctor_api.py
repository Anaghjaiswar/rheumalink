from datetime import date
import json
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from doctor.models import Doctor
from patient.models import PatientProfile
from treatment.forms import AppointmentUpdateForm, ConsultationForm, PatientDiagnosisForm, PrescriptionForm
from treatment.models import Appointment, Consultation, LabResult, LabTest, Medicine, Prescription, PrescriptionItem, jointspain, RumatDiagnosis
from treatment.views import _broadcast_queue_update, _doctor_queryset, _generate_prescription_pdf

@csrf_exempt
def get_doctor_dashboard_api(request):
    """
    GET API for Doctor Dashboard.
    Returns today's doctor appointments separated into attending, attended, and waiting,
    plus doctor list, lab reports, common tests, and search results.
    """
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Only GET allowed"}, status=405)

    doctor_id = request.GET.get("doctor_id") or request.GET.get("doctor")
    if doctor_id:
        try:
            doctor_id = int(doctor_id)
        except (ValueError, TypeError):
            doctor_id = None

    appointments = _doctor_queryset(doctor_id)

    def serialize_appt(appt):
        return {
            "id": appt.id,
            "token": f"Token {appt.token_number}",
            "token_number": appt.token_number,
            "patient_id": appt.patient_id,
            "patient_name": appt.patient.get_full_name(),
            "file": appt.patient.filerecord.internal_file_number if hasattr(appt.patient, "filerecord") else "-",
            "external_file": appt.patient.filerecord.external_file_number if (hasattr(appt.patient, "filerecord") and appt.patient.filerecord.external_file_number) else "-",
            "status": appt.get_status_display(),
            "status_code": appt.status,
            "doctor": appt.doctor.get_full_name() if appt.doctor else "Unassigned",
            "gender": appt.patient.sex or "F",
            "age": appt.patient.get_age() if hasattr(appt.patient, 'get_age') else 40,
            "contact": appt.patient.contact_no,
            "reason": appt.reason_for_visit or "General Consultation",
        }

    attending = [serialize_appt(a) for a in appointments.filter(status="I")]
    attended = [serialize_appt(a) for a in appointments.filter(status="A")]
    waiting = [serialize_appt(a) for a in appointments.filter(status="T")]

    doctors_list = []
    for d in Doctor.objects.all():
        doctors_list.append({"id": d.id, "name": d.get_full_name()})

    common_tests = list(LabTest.objects.filter(is_common=True).values("id", "name"))

    return JsonResponse({
        "ok": True,
        "selected_doctor_id": doctor_id,
        "counts": {
            "waiting": len(waiting),
            "attending": len(attending),
            "attended": len(attended),
            "total_today": appointments.count(),
        },
        "attending": attending,
        "attended": attended,
        "waiting": waiting,
        "doctors": doctors_list,
        "common_tests": common_tests,
    })


@csrf_exempt
def save_consultation_api(request, appointment_id):
    """
    POST API to save consultation notes, prescription medicines, and prescribed lab tests.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Only POST allowed"}, status=405)

    appointment = get_object_or_404(Appointment, id=appointment_id)

    try:
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST

        consultation, _ = Consultation.objects.get_or_create(
            appointment=appointment,
            defaults={"patient": appointment.patient},
        )
        consult_form = ConsultationForm(data, instance=consultation)

        prescription, _ = Prescription.objects.get_or_create(consultation=consultation)
        prescription_form = PrescriptionForm(data, instance=prescription)

        if consult_form.is_valid() and prescription_form.is_valid():
            consultation = consult_form.save(commit=False)
            consultation.patient = appointment.patient
            consultation.appointment = appointment
            consultation.save()

            prescription = prescription_form.save(commit=False)
            prescription.consultation = consultation
            prescription.save()

            test_ids = data.get("prescribed_tests", [])
            if test_ids:
                prescription.prescribed_tests.set(test_ids)

            medicines_data = data.get("items", [])
            if medicines_data:
                prescription.items.all().delete()
                for item in medicines_data:
                    med_name = item.get("medicine") or item.get("medicine_name")
                    if not med_name:
                        continue
                    med_obj, _ = Medicine.objects.get_or_create(medicine_name=med_name)
                    PrescriptionItem.objects.create(
                        prescription=prescription,
                        medicine=med_obj,
                        dosage=item.get("dosage", ""),
                        duration=item.get("duration", ""),
                        instructions=item.get("instructions", ""),
                    )

            appointment.status = data.get("post_consult_status") or "A"
            appointment.save(update_fields=["status", "updated_at"])
            _broadcast_queue_update(appointment.doctor_id)

            return JsonResponse({
                "ok": True,
                "message": "Consultation and prescription saved successfully.",
                "prescription_id": prescription.id,
                "consultation_id": consultation.id,
            })
        else:
            errors = {}
            if not consult_form.is_valid():
                errors["consultation"] = consult_form.errors
            if not prescription_form.is_valid():
                errors["prescription"] = prescription_form.errors
            return JsonResponse({"ok": False, "errors": errors}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
