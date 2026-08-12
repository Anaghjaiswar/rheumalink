import json
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from patient.models import PatientProfile
from treatment.forms import JointPainForm
from treatment.models import Appointment, jointspain
from treatment.serializers import AppointmentSerializer, JointPainSerializer, PatientProfileSerializer

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_joint_chart_api(request, appointment_id):
    """
    GET API for Joint Assessment Chart using DRF Serializers.
    Accepts appointment_id or patient_id.
    """
    try:
        appointment = Appointment.objects.select_related("patient", "doctor").filter(id=appointment_id).first()
        if appointment:
            patient = appointment.patient
            appt_data = AppointmentSerializer(appointment).data
        else:
            patient = get_object_or_404(PatientProfile, id=appointment_id)
            appt_data = None

        latest_chart = (
            jointspain.objects.filter(patient_link=patient)
            .order_by("-date_of_assessment")
            .first()
        )

        joint_states = {}
        if latest_chart:
            for field in JointPainForm().fields.keys():
                joint_states[field] = getattr(latest_chart, field, "nopain")

        recent_charts = jointspain.objects.filter(patient_link=patient).order_by("-date_of_assessment")[:6]
        recent_chart_rows = JointPainSerializer(recent_charts, many=True).data

        return Response({
            "ok": True,
            "appointment": appt_data,
            "patient": PatientProfileSerializer(patient).data,
            "latest_chart_date": latest_chart.date_of_assessment.strftime("%Y-%m-%d %H:%M") if latest_chart else None,
            "joint_states": joint_states,
            "recent_charts": recent_chart_rows,
        })
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def save_joint_chart_api(request, appointment_id):
    """
    POST API to save Joint Assessment Chart entries using JointPainSerializer.
    """
    try:
        appointment = Appointment.objects.select_related("patient").filter(id=appointment_id).first()
        if appointment:
            patient = appointment.patient
        else:
            patient = get_object_or_404(PatientProfile, id=appointment_id)

        data = request.data or {}
        form = JointPainForm(data)
        if form.is_valid():
            record = form.save(commit=False)
            record.patient_link = patient
            record.save()

            serializer = JointPainSerializer(record)
            return Response({
                "ok": True,
                "message": "Joint chart saved successfully.",
                "record_id": record.id,
                "swollen_count": serializer.data.get("swollen_count", 0),
                "tender_count": serializer.data.get("tender_count", 0),
                "chart": serializer.data,
            })
        else:
            return Response({"ok": False, "errors": form.errors}, status=400)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)
