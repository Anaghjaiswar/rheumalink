from django.core.cache import cache
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication
from clinic.models import ClinicSettings
from treatment.serializers import ClinicSettingsSerializer

@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def get_clinic_settings_api(request):
    """
    GET API to return cached ClinicSettings using ClinicSettingsSerializer.
    Publicly accessible endpoint (AllowAny).
    """
    try:
        clinic = cache.get("clinic_settings_cached")
        if clinic is None:
            clinic = ClinicSettings.objects.select_related("address").first()
            if clinic:
                cache.set("clinic_settings_cached", clinic, 300)

        if not clinic:
            clinic = ClinicSettings.objects.first()

        if not clinic:
            return Response({
                "ok": True,
                "name": "Shweta Rheumatology Clinic",
                "contact_email": "",
                "contact_number": "",
                "address": "",
                "logo_url": None,
                "is_ai_enabled": False,
            })

        serializer = ClinicSettingsSerializer(clinic)
        data = serializer.data
        return Response({
            "ok": True,
            "name": data.get("name"),
            "contact_email": data.get("contact_email") or "",
            "contact_number": data.get("contact_number") or "",
            "address": data.get("address_str") or "",
            "logo_url": data.get("logo_url"),
            "is_ai_enabled": data.get("is_ai_enabled", False),
        })
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_current_user_api(request):
    """
    GET API to return current authenticated user profile using user_id from JWT claims.
    """
    try:
        user = request.user
        role = getattr(user, "role", "DOCTOR")
        
        if role == "DOCTOR":
            from doctor.models import Doctor
            doc = Doctor.objects.filter(id=user.id).first()
            full_name = doc.get_full_name() if doc else (user.get_full_name() or f"Dr. {user.email.split('@')[0]}")
        else:
            full_name = user.get_full_name() or user.first_name or user.email.split("@")[0]

        return Response({
            "ok": True,
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": full_name,
                "role": role,
                "email": user.email or "",
            }
        })
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)
