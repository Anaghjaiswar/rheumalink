from rest_framework import serializers
from treatment.models import Appointment

class AppointmentSerializer(serializers.ModelSerializer):
    token = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    file = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "token_number",
            "token",
            "patient_id",
            "patient_name",
            "file",
            "doctor_id",
            "doctor_name",
            "status",
            "status_display",
            "reason_for_visit",
            "appointment_date",
            "appointment_time",
            "created_at",
        ]

    def get_token(self, obj):
        return f"Token {obj.token_number}"

    def get_patient_name(self, obj):
        if obj.patient:
            return obj.patient.get_full_name()
        return "Unknown Patient"

    def get_file(self, obj):
        if obj.patient and hasattr(obj.patient, "filerecord") and obj.patient.filerecord:
            return obj.patient.filerecord.internal_file_number or "-"
        return "-"

    def get_doctor_name(self, obj):
        if obj.doctor:
            return obj.doctor.get_full_name()
        return "Unassigned"
