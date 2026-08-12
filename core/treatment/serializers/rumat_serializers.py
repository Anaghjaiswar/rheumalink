from rest_framework import serializers
from patient.models import PatientDiagnosis
from treatment.models import RumatDiagnosis

class RumatDiagnosisSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = RumatDiagnosis
        fields = "__all__"

    def get_patient_name(self, obj):
        if obj.patient_link:
            return obj.patient_link.get_full_name()
        return "-"


class PatientDiagnosisSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = PatientDiagnosis
        fields = [
            "id",
            "patient_link",
            "patient_name",
            "consultation_link",
            "disease_name",
            "state",
            "version_note",
            "joints_record",
            "rumat_diagnosis",
            "date_recorded",
        ]

    def get_patient_name(self, obj):
        if obj.patient_link:
            return obj.patient_link.get_full_name()
        return "-"
