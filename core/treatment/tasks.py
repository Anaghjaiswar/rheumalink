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
    from services.ai_service_manager import AIServiceManager
    return AIServiceManager.extract_lab_report(report_id)


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
    from clinic.models import ClinicSettings
    from services.ai_service_manager import AIServiceManager

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
            report.save()
            return {"ok": False, "error": "AI Service is disabled locally.", "report_id": report.id}
            
        return AIServiceManager.extract_lab_report_pipeline(report, settings)
            
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