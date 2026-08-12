from rest_framework import serializers
from patient.models import Comorbidity, FileRecord, PatientMedicalInfo, PatientProfile

class FileRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileRecord
        fields = ["id", "internal_file_number", "external_file_number", "created_at"]


class PatientProfileSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    internal_file = serializers.SerializerMethodField()
    external_file = serializers.SerializerMethodField()

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "first_name",
            "last_name",
            "name",
            "date_of_birth",
            "sex",
            "contact_no",
            "email",
            "type",
            "internal_file",
            "external_file",
            "date_registered",
        ]

    def get_name(self, obj):
        return obj.get_full_name() or obj.email

    def get_internal_file(self, obj):
        if hasattr(obj, "filerecord") and obj.filerecord:
            return obj.filerecord.internal_file_number or "-"
        return "-"

    def get_external_file(self, obj):
        if hasattr(obj, "filerecord") and obj.filerecord:
            return obj.filerecord.external_file_number or "-"
        return "-"


class ComorbiditySerializer(serializers.ModelSerializer):
    class Meta:
        model = Comorbidity
        fields = ["id", "name"]


class PatientMedicalInfoSerializer(serializers.ModelSerializer):
    comorbidity_names = serializers.SerializerMethodField()

    class Meta:
        model = PatientMedicalInfo
        fields = [
            "id",
            "blood_group",
            "family_history",
            "known_allergies",
            "smokes",
            "alcoholic",
            "comorbidities",
            "comorbidity_names",
            "created_at",
        ]

    def get_comorbidity_names(self, obj):
        return list(obj.comorbidities.values_list("name", flat=True))
