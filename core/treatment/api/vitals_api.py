from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from treatment.forms import VitalsForm
from treatment.models import Appointment, Vitals

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_appointment_vitals_api(request, appointment_id):
    """GET API for appointment vitals."""
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

    return Response({
        "exists": True,
        "id": vitals.id,
        "weight": vitals.weight or "",
        "height": vitals.height or "",
        "bp_systolic": vitals.bp_systolic or "",
        "bp_diastolic": vitals.bp_diastolic or "",
        "pulse_rate": vitals.pulse_rate or "",
        "spo2": vitals.spo2 or "",
        "temperature": getattr(vitals, "temperature", "") or "",
        "pain_scale": vitals.pain_scale or "",
    })


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def capture_vitals_api(request, appointment_id):
    """POST API to capture or update vitals for an appointment."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    instance = Vitals.objects.filter(appointment=appointment).first()

    data = request.data
    form = VitalsForm(data, instance=instance)
    if form.is_valid():
        vitals = form.save(commit=False)
        vitals.appointment = appointment
        vitals.patient = appointment.patient
        vitals.save()
        return Response({"ok": True, "message": "Vitals saved successfully.", "vitals_id": vitals.id})
    else:
        return Response({"ok": False, "errors": form.errors}, status=400)
