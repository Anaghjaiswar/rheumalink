from rest_framework import serializers
from clinic.models import ClinicSettings

class ClinicSettingsSerializer(serializers.ModelSerializer):
    address_str = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = ClinicSettings
        fields = [
            "id",
            "name",
            "contact_email",
            "contact_number",
            "address_str",
            "logo_url",
            "is_ai_enabled",
        ]

    def get_address_str(self, obj):
        if hasattr(obj, "address") and obj.address:
            addr_parts = [
                obj.address.line1,
                obj.address.line2,
                obj.address.city,
                obj.address.state,
                obj.address.zip_code,
            ]
            return ", ".join([p for p in addr_parts if p])
        return ""

    def get_logo_url(self, obj):
        if hasattr(obj, "logo") and obj.logo:
            return obj.logo.url
        return None
