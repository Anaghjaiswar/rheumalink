from datetime import date
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from doctor.models import Doctor
from treatment.forms import ConsultationForm, PrescriptionForm
from treatment.models import Appointment, Consultation, LabTest, Medicine, Prescription, PrescriptionItem
from treatment.views import _broadcast_queue_update

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_doctor_dashboard_api(request):
    """
    GET API for Doctor Dashboard.
    Follows exact Django views.py query logic:
    Filters appointments strictly by appointment_date = date.today().
    """
    doctor_id = request.GET.get("doctor_id") or request.GET.get("doctor")
    if doctor_id:
        try:
            doctor_id = int(doctor_id)
        except (ValueError, TypeError):
            doctor_id = None

    # Exact views.py query: filter strictly by date.today()
    appointments = Appointment.objects.select_related("patient__filerecord", "doctor").filter(appointment_date=date.today())
    if doctor_id:
        appointments = appointments.filter(doctor_id=doctor_id)

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
            "appointment_date": appt.appointment_date.strftime("%Y-%m-%d"),
        }

    attending = [serialize_appt(a) for a in appointments.filter(status="I")]
    attended = [serialize_appt(a) for a in appointments.filter(status="A")]
    waiting = [serialize_appt(a) for a in appointments.filter(status="T")]

    doctors_list = []
    for d in Doctor.objects.all():
        doctors_list.append({"id": d.id, "name": d.get_full_name()})

    common_tests = list(LabTest.objects.filter(is_common=True).values("id", "name"))

    return Response({
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


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def save_consultation_api(request, appointment_id):
    """
    POST API to save consultation notes, prescription medicines, and prescribed lab tests.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)
    data = request.data

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

        return Response({
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
        return Response({"ok": False, "errors": errors}, status=400)
