from django.core.cache import cache
from django.db.models import Q
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from treatment.models import LabTest, Medicine
from treatment.serializers import LabTestSerializer, MedicineSerializer

def _safe_str(val):
    if val is None:
        return ""
    return str(val).strip()

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def medicine_autosuggest_api(request):
    """GET API for medicine autocomplete using MedicineSerializer."""
    try:
        q = _safe_str(request.GET.get("q"))
        if len(q) < 2:
            return Response({"results": []})

        cache_key = f"medicine_suggest::{q.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({"results": cached})

        medicines = (
            Medicine.objects.filter(Q(medicine_name__icontains=q) | Q(generic_name__icontains=q))[:10]
        )
        results = MedicineSerializer(medicines, many=True).data
        cache.set(cache_key, results, timeout=60 * 10)
        return Response({"results": results})
    except Exception as e:
        return Response({"results": [], "error": str(e)}, status=500)


@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def labtest_autosuggest_api(request):
    """GET API for lab test autocomplete using LabTestSerializer."""
    try:
        q = _safe_str(request.GET.get("q"))
        if len(q) < 2:
            return Response({"results": []})

        cache_key = f"labtest_suggest::{q.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({"results": cached})

        tests = LabTest.objects.filter(name__icontains=q)[:10]
        results = LabTestSerializer(tests, many=True).data
        cache.set(cache_key, results, timeout=60 * 10)
        return Response({"results": results})
    except Exception as e:
        return Response({"results": [], "error": str(e)}, status=500)
