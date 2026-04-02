import os
import json
from celery import shared_task
from .ai_service import LocalAIService
from .image_service import ImageReportProcessor
from .pdf_service import LabReportProcessor
from .models import LabResult
from django.db import transaction

def get_extension_type_of_file(file_path):
    """ checks extensions and return whether it is a image or a pdf"""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        return {"ok": True, "type": "pdf"}
    
    elif ext in ['.jpg', '.jpeg', '.png']:
        return {"ok": True, "type": "image"}
    
    else:
        return {"ok": False}
    

@shared_task(name="process_lab_report_task", queue = "primary")
def process_lab_report_task(report_id):
    "background task to extract data from report"
    try:
        health_check = LocalAIService.health_check()
        if health_check == "Offline":
            return {"ok": False, "error": "AI service is offline"}
        

        report = LabResult.objects.get(id=report_id)
        extension = get_extension_type_of_file(report.report_file.path)

        if not extension.get("ok"):
            return {"ok": False, "error": f"file format couldn't be identified. {report.report_file.path}"}
        
        report_type = extension.get("type")

        if report_type == "pdf":
            try:
                processor = LabReportProcessor()

                result = processor.process_report(report.report_file.path)

                if not result.get("ok"):
                    return {"ok": False, "error": "Error in pdf processing"}
                
                clean_json = result['extracted_json'].replace('```json', '').replace('```', '').strip()
                parsed_data = json.loads(clean_json)

                with transaction.atomic:
                    report.test_data = parsed_data
                    report.raw_ai_summary = result.get('extracted_json')
                    report.is_verified = False # doctor will verify this
                    report.save()

                return {"ok": True, "message": "Lab report processed successfully"}
            
            except Exception as e:
                return {"ok": False, "error": str(e)}
            
        elif report_type == "image":
            try:
                processor = ImageReportProcessor()
                result = processor.process_image(report.report_file.path, report.report_name)
                if not result.get("ok"):
                    return {"ok": False, "error": "Error in image processing"}  
                
                clean_data = result['extracted_json'].replace('```json', '').replace('```', '').strip()
                parsed_data = json.loads(clean_data)

                with transaction.atomic():
                    report.test_data = parsed_data
                    report.raw_ai_summary = result.get('extracted_json')
                    report.is_verified = False
                    report.save()

                return {"ok": True, "message": "Image report processed successfully"}
            except Exception as e:
                return {"ok": False, "error": str(e)}
                
    except Exception as e:
        return {"ok": False, "error": str(e)}
                    
                

            


            





        
