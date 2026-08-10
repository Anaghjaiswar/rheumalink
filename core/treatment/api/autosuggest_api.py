from django.core.cache import cache
from django.db.models import Q
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from treatment.models import LabTest, Medicine

@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def medicine_autosuggest_api(request):
    """GET API for medicine autocomplete."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return Response({"results": []})

    cache_key = f"medicine_suggest::{q.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response({"results": cached})

    medicines = (
        Medicine.objects.filter(Q(medicine_name__icontains=q) | Q(generic_name__icontains=q))
        .values("id", "medicine_name", "generic_name", "strength", "form")[:10]
    )
    results = list(medicines)
    cache.set(cache_key, results, timeout=60 * 10)
    return Response({"results": results})


@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def labtest_autosuggest_api(request):
    """GET API for lab test autocomplete."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return Response({"results": []})

    cache_key = f"labtest_suggest::{q.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response({"results": cached})

    tests = LabTest.objects.filter(name__icontains=q).values("id", "name")[:10]
    results = list(tests)
    cache.set(cache_key, results, timeout=60 * 10)
    return Response({"results": results})
