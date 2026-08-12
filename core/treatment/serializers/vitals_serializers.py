from rest_framework import serializers
from treatment.models import Vitals

class VitalsSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    date_recorded = serializers.SerializerMethodField()

    class Meta:
        model = Vitals
        fields = [
            "id",
            "appointment",
            "patient",
            "patient_name",
            "weight",
            "height",
            "bp_systolic",
            "bp_diastolic",
            "pulse_rate",
            "spo2",
            "temperature",
            "pain_scale",
            "date_recorded",
        ]

    def get_patient_name(self, obj):
        if obj.patient:
            return obj.patient.get_full_name()
        return "-"

    def get_date_recorded(self, obj):
        if obj.appointment and obj.appointment.appointment_date:
            return str(obj.appointment.appointment_date)
        return ""
