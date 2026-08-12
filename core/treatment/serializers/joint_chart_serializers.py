from rest_framework import serializers
from treatment.models import jointspain

class JointPainSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    swollen_count = serializers.SerializerMethodField()
    tender_count = serializers.SerializerMethodField()

    class Meta:
        model = jointspain
        fields = "__all__"

    def get_patient_name(self, obj):
        if obj.patient_link:
            return obj.patient_link.get_full_name()
        return "-"

    def get_swollen_count(self, obj):
        count = 0
        for field in obj._meta.fields:
            if field.name in {"id", "date_of_assessment", "patient_link"}:
                continue
            val = getattr(obj, field.name)
            if val in {"red", "orange"}:
                count += 1
        return count

    def get_tender_count(self, obj):
        count = 0
        for field in obj._meta.fields:
            if field.name in {"id", "date_of_assessment", "patient_link"}:
                continue
            val = getattr(obj, field.name)
            if val in {"blue", "orange"}:
                count += 1
        return count
