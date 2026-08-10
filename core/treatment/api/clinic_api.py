from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from clinic.models import ClinicSettings

@api_view(["GET"])
@permission_classes([AllowAny])
def get_clinic_settings_api(request):
    """
    GET API to return cached ClinicSettings from Redis DB.
    Uses cache key 'clinic_settings_cached' matching prescription PDF rendering engine.
    """
    clinic = cache.get("clinic_settings_cached")
    if clinic is None:
        clinic = ClinicSettings.objects.select_related("address").first()
        if clinic:
            cache.set("clinic_settings_cached", clinic, 300)

    if not clinic:
        return Response({
            "ok": True,
            "name": "RheumaLink",
            "contact_email": "",
            "contact_number": "",
            "address": "",
            "logo_url": None,
            "is_ai_enabled": False,
        })

    addr_str = ""
    if hasattr(clinic, "address") and clinic.address:
        addr_parts = [clinic.address.line1, clinic.address.line2, clinic.address.city, clinic.address.state, clinic.address.zip_code]
        addr_str = ", ".join([p for p in addr_parts if p])

    return Response({
        "ok": True,
        "name": clinic.name,
        "contact_email": clinic.contact_email or "",
        "contact_number": clinic.contact_number or "",
        "address": addr_str,
        "logo_url": clinic.logo.url if (hasattr(clinic, 'logo') and clinic.logo) else None,
        "is_ai_enabled": getattr(clinic, 'is_ai_enabled', False),
    })
