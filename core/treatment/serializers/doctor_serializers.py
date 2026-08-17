from rest_framework import serializers
from doctor.models import Doctor
from treatment.models import Consultation, LabTest, Medicine, Prescription, PrescriptionItem

class DoctorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = ["id", "name"]

    def get_name(self, obj):
        return obj.get_full_name() or f"Dr. {obj.first_name}"


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ["id", "name", "is_common"]


class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = ["id", "medicine_name", "generic_name", "strength", "form"]


class PrescriptionItemSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.medicine_name", read_only=True)

    class Meta:
        model = PrescriptionItem
        fields = ["id", "medicine", "medicine_name", "dosage", "duration", "instructions"]


class PrescriptionSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True, read_only=True)
    prescribed_tests = LabTestSerializer(many=True, read_only=True)

    class Meta:
        model = Prescription
        fields = [
            "id",
            "consultation",
            "prescription_pdf",
            "items",
            "prescribed_tests",
            "advice_notes",
            "lab_investigations",
            "next_followup_date",
        ]


class ConsultationSerializer(serializers.ModelSerializer):
    prescription = PrescriptionSerializer(read_only=True)
    diagnosis = serializers.CharField(source="provisional_diagnosis", read_only=True)

    class Meta:
        model = Consultation
        fields = [
            "id",
            "patient",
            "appointment",
            "chief_complaints",
            "clinical_findings",
            "provisional_diagnosis",
            "diagnosis",
            "prescription",
            "created_at",
        ]
