import os
import json
import base64
import requests # type:ignore
import logging
from celery import shared_task
from django.db import transaction
from .models import LabResult
from clinic.models import ClinicSettings

logger = logging.getLogger(__name__)

def get_file_metadata(file_path):
    """File extension check karke correct MIME type return karta hai."""
    ext = os.path.splitext(file_path)[1].lower()
    mapping = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png'
    }
    return mapping.get(ext)

@shared_task(name="process_lab_report_task", queue="primary")
def process_lab_report_task(report_id):
    """
    Background task to extract data using the Cloud AI Service.
    """
    try:
        # 1. Fetch Report and Clinic Settings
        report = LabResult.objects.get(id=report_id)
        settings = ClinicSettings.objects.first() # Humne model mein yahi banaya tha
        
        if not settings or not settings.is_ai_enabled:
            return {"ok": False, "error": "AI Service is disabled locally or not configured."}

        # 2. File and MIME Check
        mime_type = get_file_metadata(report.report_file.path)
        if not mime_type:
            return {"ok": False, "error": "Unsupported file format."}

        # 3. Convert File to Base64
        with open(report.report_file.path, "rb") as f:
            encoded_file = base64.b64encode(f.read()).decode("utf-8")

        # 4. Call Cloud AI Service
        # Droplet ka URL yahan aayega (v1/extract endpoint)
        AI_URL = "http://127.0.0.1:8001/v1/extract" 
        
        headers = {
            "X-Clinic-Key": settings.api_access_token,
            "Content-Type": "application/json"
        }
        
        payload = {
            "image_base64": encoded_file,
            "report_type": report.report_name, # e.g., 'CBC', 'ESR'
            "mime_type": mime_type
        }

        response = requests.post(AI_URL, json=payload, headers=headers, timeout=60)

        # 5. Handle Kill-Switch / Unauthorized
        if response.status_code == 401 or response.status_code == 402:
            # Subscription expired logic
            with transaction.atomic():
                settings.is_ai_enabled = False
                settings.save()
            return {"ok": False, "error": f"AI Service access denied: {response.status_code}"}

        if response.status_code != 200:
            return {"ok": False, "error": f"Cloud Service Error: {response.text}"}

        # 6. Process and Save Result
        result = response.json()
        if result.get("ok"):
            structured_data = result.get("data") # AI service already cleans JSON
            
            with transaction.atomic():
                report.test_data = structured_data
                report.is_verified = False
                report.save()
            
            return {"ok": True, "message": "Cloud extraction successful"}
        
        return {"ok": False, "error": result.get("error")}

    except LabResult.DoesNotExist:
        return {"ok": False, "error": "Report ID not found"}
    except Exception as e:
        logger.error(f"Task Error: {str(e)}")
        return {"ok": False, "error": str(e)}