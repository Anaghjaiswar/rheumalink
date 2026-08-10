import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from patient.models import PatientDiagnosis
from treatment.forms import RumatDiagnosisForm
from treatment.models import Appointment, Consultation, LabResult, RumatDiagnosis

@csrf_exempt
def get_rumat_diagnosis_api(request, appointment_id):
    """
    GET API for Rheumat Diagnosis Checklist & AI Notes.
    Returns patient summary, latest RumatDiagnosis data, existing PatientDiagnosis record, and latest lab data.
    """
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Only GET allowed"}, status=405)

    appointment = get_object_or_404(Appointment.objects.select_related("patient", "doctor"), id=appointment_id)
    patient = appointment.patient

    latest_diagnosis = RumatDiagnosis.objects.filter(patient_link=patient).last()
    
    checklist_data = {}
    if latest_diagnosis:
        for field in RumatDiagnosisForm().fields.keys():
            checklist_data[field] = getattr(latest_diagnosis, field, None)

    consultation = Consultation.objects.filter(appointment=appointment).first()
    existing_patient_diag = PatientDiagnosis.objects.filter(consultation_link=consultation).first() if consultation else None

    latest_lab = LabResult.objects.filter(patient=patient).exclude(test_data={}).first()

    return JsonResponse({
        "ok": True,
        "appointment": {
            "id": appointment.id,
            "token_number": appointment.token_number,
            "date": appointment.appointment_date.strftime("%Y-%m-%d"),
            "doctor_name": appointment.doctor.get_full_name() if appointment.doctor else "Unassigned",
        },
        "patient": {
            "id": patient.id,
            "name": patient.get_full_name(),
            "sex": patient.sex,
            "age": patient.get_age() if hasattr(patient, 'get_age') else "",
            "internal_file": patient.filerecord.internal_file_number if hasattr(patient, 'filerecord') else "-",
        },
        "disease_name": existing_patient_diag.disease_name if existing_patient_diag else "Rheumatoid Arthritis",
        "disease_state": existing_patient_diag.state if existing_patient_diag else "Active",
        "version_note": existing_patient_diag.version_note if existing_patient_diag else "",
        "checklist_data": checklist_data,
        "latest_lab_data": latest_lab.test_data if (latest_lab and latest_lab.test_data) else {},
    })


@csrf_exempt
def save_rumat_diagnosis_api(request, appointment_id):
    """
    POST API to save Rheumat Diagnosis checklist, update PatientDiagnosis and Consultation link.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Only POST allowed"}, status=405)

    appointment = get_object_or_404(Appointment.objects.select_related("patient"), id=appointment_id)
    patient = appointment.patient

    try:
        if request.content_type == "application/json":
            data = json.loads(request.body)
        else:
            data = request.POST

        form = RumatDiagnosisForm(data)
        if form.is_valid():
            rumat_diag = form.save(commit=False)
            rumat_diag.patient_link = patient
            rumat_diag.save()

            consultation, _ = Consultation.objects.get_or_create(
                appointment=appointment,
                defaults={"patient": patient}
            )

            patient_diag = PatientDiagnosis.objects.filter(consultation_link=consultation).first()
            if not patient_diag:
                patient_diag = PatientDiagnosis(
                    patient_link=patient,
                    consultation_link=consultation,
                    disease_name="Rheumatoid Arthritis",
                )
            patient_diag.rumat_diagnosis = rumat_diag

            desc_lower = (rumat_diag.description_t or "").lower()
            if "lupus" in desc_lower or "sle" in desc_lower:
                patient_diag.disease_name = "Lupus (SLE)"
            elif "gout" in desc_lower:
                patient_diag.disease_name = "Gout"
            elif "ankylosing" in desc_lower:
                patient_diag.disease_name = "Ankylosing Spondylitis"
            elif "psoriatic" in desc_lower:
                patient_diag.disease_name = "Psoriatic Arthritis"

            if data.get("disease_name"):
                patient_diag.disease_name = data.get("disease_name")
            if data.get("state"):
                patient_diag.state = data.get("state")
            if data.get("version_note"):
                patient_diag.version_note = data.get("version_note")

            patient_diag.save()

            return JsonResponse({
                "ok": True,
                "message": "Rheumat Diagnosis saved successfully.",
                "rumat_diagnosis_id": rumat_diag.id,
                "disease_name": patient_diag.disease_name,
                "disease_state": patient_diag.state,
            })
        else:
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
