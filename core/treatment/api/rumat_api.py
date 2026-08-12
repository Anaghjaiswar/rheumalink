from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from patient.models import PatientDiagnosis, PatientProfile
from treatment.forms import RumatDiagnosisForm
from treatment.models import Appointment, Consultation, LabResult, RumatDiagnosis
from treatment.serializers import (
    AppointmentSerializer,
    PatientDiagnosisSerializer,
    PatientProfileSerializer,
    RumatDiagnosisSerializer,
)

def _safe_str(val):
    if val is None:
        return ""
    return str(val).strip()

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_rumat_diagnosis_api(request, appointment_id):
    """
    GET API for Rheumat Diagnosis Checklist & AI Notes utilizing DRF Serializers.
    """
    try:
        appointment = Appointment.objects.select_related("patient", "doctor").filter(id=appointment_id).first()
        if appointment:
            patient = appointment.patient
            appt_data = AppointmentSerializer(appointment).data
        else:
            patient = get_object_or_404(PatientProfile, id=appointment_id)
            appt_data = None

        latest_diagnosis = RumatDiagnosis.objects.filter(patient_link=patient).last()
        
        checklist_data = RumatDiagnosisSerializer(latest_diagnosis).data if latest_diagnosis else {}

        consultation = Consultation.objects.filter(appointment=appointment).first() if appointment else None
        existing_patient_diag = PatientDiagnosis.objects.filter(consultation_link=consultation).first() if consultation else PatientDiagnosis.objects.filter(patient_link=patient).first()

        latest_lab = LabResult.objects.filter(patient=patient).exclude(test_data={}).first()

        return Response({
            "ok": True,
            "appointment": appt_data,
            "patient": PatientProfileSerializer(patient).data,
            "disease_name": existing_patient_diag.disease_name if existing_patient_diag else "Rheumatoid Arthritis",
            "disease_state": existing_patient_diag.state if existing_patient_diag else "Active",
            "version_note": existing_patient_diag.version_note if existing_patient_diag else "",
            "checklist_data": checklist_data,
            "latest_lab_data": latest_lab.test_data if (latest_lab and latest_lab.test_data) else {},
        })
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def save_rumat_diagnosis_api(request, appointment_id):
    """
    POST API to save Rheumat Diagnosis checklist using RumatDiagnosisSerializer and PatientDiagnosisSerializer.
    """
    try:
        appointment = Appointment.objects.select_related("patient").filter(id=appointment_id).first()
        if appointment:
            patient = appointment.patient
        else:
            patient = get_object_or_404(PatientProfile, id=appointment_id)

        data = request.data or {}
        form = RumatDiagnosisForm(data)
        if form.is_valid():
            rumat_diag = form.save(commit=False)
            rumat_diag.patient_link = patient
            rumat_diag.save()

            if appointment:
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

                desc_lower = _safe_str(rumat_diag.description_t).lower()
                if "lupus" in desc_lower or "sle" in desc_lower:
                    patient_diag.disease_name = "Lupus (SLE)"
                elif "gout" in desc_lower:
                    patient_diag.disease_name = "Gout"
                elif "ankylosing" in desc_lower:
                    patient_diag.disease_name = "Ankylosing Spondylitis"
                elif "psoriatic" in desc_lower:
                    patient_diag.disease_name = "Psoriatic Arthritis"

                if data.get("disease_name"):
                    patient_diag.disease_name = _safe_str(data.get("disease_name"))
                if data.get("state"):
                    patient_diag.state = _safe_str(data.get("state"))
                if data.get("version_note"):
                    patient_diag.version_note = _safe_str(data.get("version_note"))

                patient_diag.save()
                disease_name = patient_diag.disease_name
                disease_state = patient_diag.state
            else:
                disease_name = _safe_str(data.get("disease_name")) or "Rheumatoid Arthritis"
                disease_state = _safe_str(data.get("state")) or "Active"

            return Response({
                "ok": True,
                "message": "Rheumat Diagnosis saved successfully.",
                "rumat_diagnosis": RumatDiagnosisSerializer(rumat_diag).data,
                "disease_name": disease_name,
                "disease_state": disease_state,
            })
        else:
            return Response({"ok": False, "errors": form.errors}, status=400)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)
