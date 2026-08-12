from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from patient.models import Comorbidity, PatientMedicalInfo, PatientProfile
from treatment.forms import PatientMedicalInfoForm
from treatment.serializers import ComorbiditySerializer, PatientMedicalInfoSerializer

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_patient_medical_info_api(request, patient_id):
    """
    GET API for patient medical history utilizing DRF Serializers.
    """
    try:
        patient = get_object_or_404(PatientProfile, id=patient_id)
        medical_info = PatientMedicalInfo.objects.filter(patient=patient).order_by('-created_at', '-id').first()
        
        all_comorbidities = ComorbiditySerializer(Comorbidity.objects.all(), many=True).data

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

        data = PatientMedicalInfoSerializer(medical_info).data
        data["exists"] = True
        data["all_comorbidities"] = all_comorbidities
        return Response(data)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def save_patient_medical_info_api(request, patient_id):
    """
    POST API to save new version of patient medical info wrapped in atomic transaction block.
    """
    try:
        patient = get_object_or_404(PatientProfile, id=patient_id)
        data = request.data or {}
        form = PatientMedicalInfoForm(data)
        if form.is_valid():
            with transaction.atomic():
                medical_info = form.save(commit=False)
                medical_info.id = None
                medical_info.patient = patient
                medical_info.save()
                form.save_m2m()

                custom = form.cleaned_data.get("custom_comorbidity")
                if custom:
                    comorbidity, _ = Comorbidity.objects.get_or_create(name=custom.strip())
                    medical_info.comorbidities.add(comorbidity)

            serializer = PatientMedicalInfoSerializer(medical_info)
            return Response({
                "ok": True,
                "message": f"Medical info for {patient.get_full_name()} saved as a new version.",
                "medical_info_id": medical_info.id,
                "medical_info": serializer.data,
            })
        else:
            return Response({"ok": False, "errors": form.errors}, status=400)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)
