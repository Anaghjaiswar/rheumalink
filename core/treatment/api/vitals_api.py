from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from treatment.forms import VitalsForm
from treatment.models import Appointment, Vitals
from treatment.serializers import VitalsSerializer, AppointmentSerializer

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_patient_appointments_api(request, patient_id):
    """GET API to return all appointments for a given patient profile."""
    try:
        appts = Appointment.objects.select_related("doctor", "patient").filter(patient_id=patient_id).order_by("-appointment_date", "-appointment_time")
        serializer = AppointmentSerializer(appts, many=True)
        return Response({"ok": True, "appointments": serializer.data})
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_appointment_vitals_api(request, appointment_id):
    """GET API for appointment vitals using VitalsSerializer."""
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        vitals = Vitals.objects.filter(appointment=appointment).first()
        if not vitals:
            return Response({
                "exists": False,
                "weight": "",
                "height": "",
                "bp_systolic": "",
                "bp_diastolic": "",
                "pulse_rate": "",
                "spo2": "",
                "temperature": "",
                "pain_scale": "",
            })

        serializer = VitalsSerializer(vitals)
        data = serializer.data
        data["exists"] = True
        return Response(data)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def capture_vitals_api(request, appointment_id):
    """POST API to capture or update vitals using VitalsSerializer."""
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        instance = Vitals.objects.filter(appointment=appointment).first()

        data = request.data or {}
        form = VitalsForm(data, instance=instance)
        if form.is_valid():
            vitals = form.save(commit=False)
            vitals.appointment = appointment
            vitals.patient = appointment.patient
            vitals.save()
            serializer = VitalsSerializer(vitals)
            return Response({"ok": True, "message": "Vitals saved successfully.", "vitals_id": vitals.id, "vitals": serializer.data})
        else:
            return Response({"ok": False, "errors": form.errors}, status=400)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)
