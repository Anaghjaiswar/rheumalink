import json
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from treatment.forms import JointPainForm
from treatment.models import Appointment, jointspain

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_joint_chart_api(request, appointment_id):
    """
    GET API for Joint Assessment Chart.
    Requires JWT or Session authentication.
    """
    appointment = get_object_or_404(Appointment.objects.select_related("patient", "doctor"), id=appointment_id)
    patient = appointment.patient

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
    recent_chart_rows = []
    for chart in recent_charts:
        swollen = 0
        tender = 0
        for field in chart._meta.fields:
            name = field.name
            if name in {"id", "date_of_assessment", "patient_link"}:
                continue
            val = getattr(chart, name)
            if val == "red":
                swollen += 1
            elif val == "blue":
                tender += 1
            elif val == "orange":
                swollen += 1
                tender += 1
        recent_chart_rows.append({
            "id": chart.id,
            "recorded_at": chart.date_of_assessment.strftime("%d %b %Y %I:%M %p") if chart.date_of_assessment else "",
            "swollen": swollen,
            "tender": tender,
        })

    return Response({
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
            "internal_file": patient.filerecord.internal_file_number if hasattr(patient, 'filerecord') else "-",
        },
        "latest_chart_date": latest_chart.date_of_assessment.strftime("%Y-%m-%d %H:%M") if latest_chart else None,
        "joint_states": joint_states,
        "recent_charts": recent_chart_rows,
    })


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def save_joint_chart_api(request, appointment_id):
    """
    POST API to save Joint Assessment Chart entries.
    Requires JWT or Session authentication.
    """
    appointment = get_object_or_404(Appointment.objects.select_related("patient"), id=appointment_id)
    patient = appointment.patient

    data = request.data
    form = JointPainForm(data)
    if form.is_valid():
        record = form.save(commit=False)
        record.patient_link = patient
        record.save()

        swollen = 0
        tender = 0
        for field in record._meta.fields:
            name = field.name
            if name in {"id", "date_of_assessment", "patient_link"}:
                continue
            val = getattr(record, name)
            if val == "red":
                swollen += 1
            elif val == "blue":
                tender += 1
            elif val == "orange":
                swollen += 1
                tender += 1

        return Response({
            "ok": True,
            "message": "Joint chart saved successfully.",
            "record_id": record.id,
            "swollen_count": swollen,
            "tender_count": tender,
        })
    else:
        return Response({"ok": False, "errors": form.errors}, status=400)
