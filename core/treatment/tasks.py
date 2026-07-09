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


@shared_task(name="process_lab_report_pipeline_task", queue="primary")
def process_lab_report_pipeline_task(patient_id, appointment_id, report_name, test_date_str, temp_file_path):
    """
    Background Celery task to:
    1. Create LabResult instance.
    2. Upload PDF to MinIO bucket.
    3. Call the AI microservice endpoint to extract clinical JSON.
    4. Save extraction to test_data.
    """
    from patient.models import PatientProfile
    from .models import Appointment, LabResult
    from django.core.files import File
    import os
    import requests
    from clinic.models import ClinicSettings

    try:
        patient = PatientProfile.objects.get(id=patient_id)
        appointment = Appointment.objects.get(id=appointment_id) if appointment_id else None
        
        # 1. Create the LabResult instance
        report = LabResult(
            patient=patient,
            appointment=appointment,
            report_name=report_name,
            test_date=test_date_str if test_date_str else None,
        )
        
        # 2. Upload file to MinIO (by saving to report_file which uses LabReportStorage)
        with open(temp_file_path, 'rb') as f:
            django_file = File(f)
            # This triggers S3Storage/MinioStorage upload to 'lab-reports' bucket
            report.report_file.save(os.path.basename(temp_file_path), django_file, save=True)
            
        # Delete temporary local file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
                
        # 3. Call central ai_service microservice to extract clinical data
        settings = ClinicSettings.objects.first()
        if not settings or not settings.is_ai_enabled:
            return {"ok": False, "error": "AI Service is disabled locally.", "report_id": report.id}
            
        # We read the file bytes to send
        report.report_file.seek(0)
        file_bytes = report.report_file.read()
        
        # Call central ai_service microservice endpoint `/v1/extract-lab-report`
        AI_URL = "http://ai_service:8001/v1/extract-lab-report"
        headers = {
            "x-clinic-key": settings.api_access_token if settings else ""
        }
        files = {
            "file": (os.path.basename(report.report_file.name), file_bytes, "application/pdf")
        }
        
        response = requests.post(AI_URL, headers=headers, files=files, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                data = result.get("data")
                
                # Format extracted tests into the model's test_data JSON:
                # Format: {"ESR": {"value": 45, "unit": "mm/hr"}, "CRP": {"value": 12, "unit": "mg/L"}}
                formatted_data = {}
                extracted_tests = data.get("tests", [])
                for t in extracted_tests:
                    name = t.get("test_name")
                    val = t.get("result_value")
                    unit = t.get("unit")
                    ref = t.get("reference_interval")
                    
                    formatted_data[name] = {
                        "value": val,
                        "unit": unit
                    }
                    if ref:
                        formatted_data[name]["reference_interval"] = ref
                        
                report.test_data = formatted_data
                report.raw_ai_summary = data
                report.save()
                return {"ok": True, "report_id": report.id, "data": formatted_data}
            else:
                # Save empty test_data but report is still created
                report.save()
                return {"ok": False, "error": result.get("error"), "report_id": report.id}
        else:
            report.save()
            return {"ok": False, "error": f"Cloud Service Error status {response.status_code}", "report_id": report.id}
            
    except Exception as e:
        logger.error(f"Error in process_lab_report_pipeline_task: {str(e)}")
        return {"ok": False, "error": str(e)}


@shared_task(name="cleanup_unverified_lab_reports_task", queue="primary")
def cleanup_unverified_lab_reports_task():
    """
    Periodic task running every 3 hours to clean up unverified LabResult records
    (where is_verified is False and created_at is older than 3 hours), 
    and delete their associated PDF files from MinIO.
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import LabResult

    try:
        cutoff = timezone.now() - timedelta(hours=3)
        # Find all unverified lab reports older than 3 hours
        unverified_reports = LabResult.objects.filter(is_verified=False, created_at__lt=cutoff)
        
        count = 0
        for report in unverified_reports:
            # Delete file from MinIO storage
            if report.report_file:
                try:
                    report.report_file.delete(save=False)
                except Exception as file_err:
                    logger.error(f"Error deleting file from MinIO for LabResult {report.id}: {file_err}")
            
            # Delete database record
            report.delete()
            count += 1
            
        logger.info(f"Successfully cleaned up {count} unverified lab reports from MinIO and database.")
        return f"Cleaned up {count} reports."
    except Exception as e:
        logger.error(f"Error in cleanup_unverified_lab_reports_task: {str(e)}")
        return f"Error: {str(e)}"