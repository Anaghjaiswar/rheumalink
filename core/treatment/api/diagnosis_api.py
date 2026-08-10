from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from patient.models import PatientDiagnosis
from treatment.forms import PatientDiagnosisForm
from treatment.models import Appointment, Consultation, RumatDiagnosis, jointspain
from treatment.services import RheumaAnalyticsService

@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def save_diagnosis_api(request, appointment_id):
    """
    POST API to save Patient Diagnosis linking latest joint chart and rheumat diagnosis.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)
    consultation = Consultation.objects.filter(appointment=appointment).first()
    if not consultation:
        consultation = Consultation.objects.create(patient=appointment.patient, appointment=appointment)

    existing_diag = PatientDiagnosis.objects.filter(consultation_link=consultation).first()
    data = request.data
    form = PatientDiagnosisForm(data, instance=existing_diag)

    if form.is_valid():
        joint_record = (
            jointspain.objects.filter(patient_link=appointment.patient)
            .order_by("-date_of_assessment")
            .first()
        )

        rumat_diagnosis = (
            RumatDiagnosis.objects.filter(patient_link=appointment.patient)
            .order_by("-id")
            .first()
        )

        diagnosis = form.save(commit=False)
        diagnosis.patient_link = appointment.patient
        diagnosis.consultation_link = consultation
        diagnosis.joints_record = joint_record
        diagnosis.rumat_diagnosis = rumat_diagnosis
        diagnosis.save()

        return Response({
            "ok": True,
            "message": "Patient diagnosis saved successfully.",
            "has_joint_chart": bool(joint_record),
            "has_rumat_checklist": bool(rumat_diagnosis),
            "diagnosis_id": diagnosis.id,
        })
    else:
        return Response({"ok": False, "errors": form.errors}, status=400)


@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def das28_score_api(request, appointment_id):
    """GET API to calculate DAS28 score for an appointment."""
    data = RheumaAnalyticsService.calculate_das28_score(appointment_id)
    return Response(data)
