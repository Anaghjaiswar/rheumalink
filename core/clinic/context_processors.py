from .models import ClinicSettings

def clinic_context(request):
    """Context processor to make clinic settings available across all templates."""
    return {
        'clinic': ClinicSettings.objects.first()
    }
