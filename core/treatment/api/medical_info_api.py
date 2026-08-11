from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from patient.models import Comorbidity, PatientMedicalInfo, PatientProfile
from treatment.forms import PatientMedicalInfoForm

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_patient_medical_info_api(request, patient_id):
    """
    GET API for patient medical history & database comorbidities list.
    Queries database directly for all available Comorbidity objects.
    """
    patient = get_object_or_404(PatientProfile, id=patient_id)
    medical_info = PatientMedicalInfo.objects.filter(patient=patient).order_by('-created_at', '-id').first()
    
    all_comorbidities = list(Comorbidity.objects.all().values("id", "name"))

    if not medical_info:
        return Response({
            "exists": False,
            "blood_group": "",
            "family_history": "",
            "known_allergies": "",
            "smokes": False,
            "alcoholic": False,
            "comorbidities": [],
            "comorbidity_names": [],
            "all_comorbidities": all_comorbidities,
            "created_at": "",
        })

    created_at_str = ""
    if getattr(medical_info, 'created_at', None):
        created_at_str = medical_info.created_at.strftime("%d %b %Y, %I:%M %p")

    return Response({
        "exists": True,
        "id": medical_info.id,
        "blood_group": medical_info.blood_group,
        "family_history": medical_info.family_history or "",
        "known_allergies": medical_info.known_allergies or "",
        "smokes": medical_info.smokes,
        "alcoholic": getattr(medical_info, 'alcohololic', False),
        "comorbidities": list(medical_info.comorbidities.values_list("id", flat=True)),
        "comorbidity_names": list(medical_info.comorbidities.values_list("name", flat=True)),
        "all_comorbidities": all_comorbidities,
        "created_at": created_at_str,
    })


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def save_patient_medical_info_api(request, patient_id):
    """
    POST API to save new version of patient medical info with custom comorbidities.
    """
    patient = get_object_or_404(PatientProfile, id=patient_id)
    data = request.data
    form = PatientMedicalInfoForm(data)
    if form.is_valid():
        medical_info = form.save(commit=False)
        medical_info.id = None
        medical_info.patient = patient
        medical_info.save()
        form.save_m2m()

        custom = form.cleaned_data.get("custom_comorbidity")
        if custom:
            comorbidity, _ = Comorbidity.objects.get_or_create(name=custom.strip())
            medical_info.comorbidities.add(comorbidity)

        return Response({
            "ok": True,
            "message": f"Medical info for {patient.get_full_name()} saved as a new version.",
            "medical_info_id": medical_info.id,
        })
    else:
        return Response({"ok": False, "errors": form.errors}, status=400)
