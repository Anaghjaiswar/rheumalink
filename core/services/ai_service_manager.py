import os
import json
import base64
import requests
import logging
import difflib

from django.views import View
from django.http import JsonResponse, StreamingHttpResponse
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from treatment.models import LabResult, Appointment, LabTest, Medicine
from clinic.models import ClinicSettings
from patient.models import PatientProfile

logger = logging.getLogger(__name__)


def get_file_metadata(file_path):
    """Returns correct MIME type based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    mapping = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png'
    }
    return mapping.get(ext)


@method_decorator(csrf_exempt, name='dispatch')
class AIServiceManager(View):
    """
    Centralized Class-Based View and Service Manager for all AI tasks.
    Exposes action-based routing for frontend calls, and classmethods for backend tasks.
    """
    action = None

    def dispatch(self, request, *args, **kwargs):
        if self.action:
            handler = getattr(self, self.action, None)
            if handler:
                return handler(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    # -------------------------------------------------------------
    # Frontend Views (Routed via urls.py using action kwargs)
    # -------------------------------------------------------------

    def generate_rumat_summary(self, request, appointment_id):
        """
        Generates clinical summary of Rumatology findings in streaming format.
        """
        if request.method != "POST":
            return JsonResponse({"error": "Only POST requests allowed"}, status=405)

        try:
            appointment = get_object_or_404(Appointment.objects.select_related("patient"), id=appointment_id)
            patient = appointment.patient

            body = json.loads(request.body)
            findings = body.get("findings", {})

            age = patient.get_age()
            sex = patient.sex
            sex_str = "male" if sex == "M" else "female"

            settings = ClinicSettings.objects.first()

            if not settings or not settings.is_ai_enabled:
                def stream_unsubscribed():
                    yield "AI Summary Service is not active. Please subscribe to enable this feature."
                return StreamingHttpResponse(stream_unsubscribed(), content_type="text/plain")

            try:
                # Call central ai_service container endpoint `/v1/rumat-summary` (Streaming)
                AI_URL = "http://ai_service:8001/v1/rumat-summary"
                headers = {
                    "X-Clinic-Key": settings.api_access_token,
                    "Content-Type": "application/json"
                }
                payload = {
                    "age": age,
                    "sex": sex_str,
                    "findings": findings
                }
                response = requests.post(AI_URL, json=payload, headers=headers, timeout=15, stream=True)
                if response.status_code == 200:
                    def stream_response():
                        for chunk in response.iter_content(chunk_size=512, decode_unicode=True):
                            if chunk:
                                yield chunk
                    return StreamingHttpResponse(stream_response(), content_type="text/plain")
                else:
                    def stream_api_error():
                        yield f"AI Service returned error {response.status_code}. Please contact support."
                    return StreamingHttpResponse(stream_api_error(), content_type="text/plain")
            except Exception:
                def stream_conn_error():
                    yield "AI Service is temporarily unreachable. Please check your connection and try again."
                return StreamingHttpResponse(stream_conn_error(), content_type="text/plain")

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    def correct_transcription(self, request):
        """
        Proxies spelling and terminology correction requests to the internal ai_service.
        """
        if request.method != "POST":
            return JsonResponse({"error": "Only POST requests allowed"}, status=405)

        try:
            settings_obj = ClinicSettings.objects.first()
            if not settings_obj or not settings_obj.api_access_token:
                return JsonResponse({"ok": False, "error": "Clinic settings or API key not found in Django."}, status=400)

            body = json.loads(request.body)
            text = body.get("text", "")

            # Call internal ai_service container endpoint `/v1/correct-transcription`
            url = "http://ai_service:8001/v1/correct-transcription"
            headers = {
                "x-clinic-key": settings_obj.api_access_token,
                "Content-Type": "application/json"
            }
            payload = {"text": text}

            response = requests.post(url, json=payload, headers=headers, timeout=60)
            logger.info(f"response of AI Service: {response.text}")
            if response.status_code == 200:
                return JsonResponse(response.json())
            else:
                return JsonResponse({"ok": False, "error": f"AI Service returned HTTP {response.status_code}: {response.text}"}, status=response.status_code)
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=500)

    def structure_clinical_note(self, request):
        """
        Proxies clinical note structuring requests to the internal ai_service
        and resolves/creates prescribed tests and medicines in the database.
        """
        if request.method != "POST":
            return JsonResponse({"error": "Only POST requests allowed"}, status=405)

        try:
            settings_obj = ClinicSettings.objects.first()
            if not settings_obj or not settings_obj.api_access_token:
                return JsonResponse({"ok": False, "error": "Clinic settings or API key not found in Django."}, status=400)

            body = json.loads(request.body)
            text = body.get("text", "")

            # Call internal ai_service container endpoint `/v1/structure-clinical-note`
            url = "http://ai_service:8001/v1/structure-clinical-note"
            headers = {
                "x-clinic-key": settings_obj.api_access_token,
                "Content-Type": "application/json"
            }
            payload = {"text": text}

            response = requests.post(url, json=payload, headers=headers, timeout=60)
            logger.info(f"response of AI Service: {response.text}")
            if response.status_code == 200:
                resp_data = response.json()

                if resp_data.get("ok") and resp_data.get("data"):
                    extracted_data = resp_data.get("data")

                    # 1. Resolve and dynamically create Prescribed Lab Tests in the DB
                    prescribed_tests = extracted_data.get("prescribed_tests", [])
                    resolved_tests = []
                    for test_name in prescribed_tests:
                        test_name_clean = test_name.strip()
                        if not test_name_clean:
                            continue

                        # Case-insensitive iexact match
                        test_obj = LabTest.objects.filter(name__iexact=test_name_clean).first()
                        if not test_obj:
                            # Substring match fallback
                            test_obj = LabTest.objects.filter(name__icontains=test_name_clean).first()
                        if not test_obj:
                            # Create new LabTest
                            test_obj = LabTest.objects.create(name=test_name_clean, is_common=False)

                        resolved_tests.append({
                            "id": test_obj.id,
                            "name": test_obj.name
                        })
                    extracted_data["prescribed_tests"] = resolved_tests

                    # 2. Resolve and dynamically create Medicines in the DB
                    medicines_dict = extracted_data.get("medicines", {})
                    resolved_medicines = {}
                    for med_name, med_info in medicines_dict.items():
                        med_name_clean = med_name.strip()
                        if not med_name_clean:
                            continue

                        # Case-insensitive iexact match
                        med_obj = Medicine.objects.filter(medicine_name__iexact=med_name_clean).first()
                        if not med_obj:
                            # Substring match fallback
                            med_obj = Medicine.objects.filter(medicine_name__icontains=med_name_clean).first()
                        if not med_obj:
                            # Generic name iexact match fallback
                            med_obj = Medicine.objects.filter(generic_name__iexact=med_name_clean).first()
                        if not med_obj:
                            # Dynamic fuzzy match fallback using standard difflib
                            db_names = list(Medicine.objects.values_list('medicine_name', flat=True))
                            db_generics = list(Medicine.objects.exclude(generic_name__isnull=True).exclude(generic_name="").values_list('generic_name', flat=True))
                            possibilities = list(set(db_names + db_generics))

                            close_matches = difflib.get_close_matches(med_name_clean, possibilities, n=1, cutoff=0.6)
                            if close_matches:
                                matched_name = close_matches[0]
                                med_obj = Medicine.objects.filter(medicine_name=matched_name).first()
                                if not med_obj:
                                    med_obj = Medicine.objects.filter(generic_name=matched_name).first()
                        if not med_obj:
                            # Create new Medicine record in inventory
                            med_obj = Medicine.objects.create(
                                medicine_name=med_name_clean,
                                generic_name=med_name_clean,
                                form='Tablet',
                                category='General'
                            )

                        resolved_medicines[med_name_clean] = {
                            "id": med_obj.id,
                            "medicine_name": med_obj.medicine_name,
                            "dosage": med_info.get("dosage", ""),
                            "duration": med_info.get("duration", ""),
                            "instructions": med_info.get("instructions", "")
                        }
                    extracted_data["medicines"] = resolved_medicines

                return JsonResponse(resp_data)
            else:
                return JsonResponse({"ok": False, "error": f"AI Service returned HTTP {response.status_code}: {response.text}"}, status=response.status_code)
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=500)

    # -------------------------------------------------------------
    # Backend Helper Functions (Callable directly within project code)
    # -------------------------------------------------------------

    @classmethod
    def extract_lab_report(cls, report_id):
        """
        Calls the Cloud AI Service (v1/extract endpoint) to extract data from a lab report image/PDF.
        """
        try:
            report = LabResult.objects.get(id=report_id)
            settings = ClinicSettings.objects.first()

            if not settings or not settings.is_ai_enabled:
                return {"ok": False, "error": "AI Service is disabled locally or not configured."}

            mime_type = get_file_metadata(report.report_file.path)
            if not mime_type:
                return {"ok": False, "error": "Unsupported file format."}

            with open(report.report_file.path, "rb") as f:
                encoded_file = base64.b64encode(f.read()).decode("utf-8")

            AI_URL = "http://127.0.0.1:8001/v1/extract"

            headers = {
                "X-Clinic-Key": settings.api_access_token,
                "Content-Type": "application/json"
            }

            payload = {
                "image_base64": encoded_file,
                "report_type": report.report_name,
                "mime_type": mime_type
            }

            response = requests.post(AI_URL, json=payload, headers=headers, timeout=60)

            if response.status_code in (401, 402):
                with transaction.atomic():
                    settings.is_ai_enabled = False
                    settings.save()
                return {"ok": False, "error": f"AI Service access denied: {response.status_code}"}

            if response.status_code != 200:
                return {"ok": False, "error": f"Cloud Service Error: {response.text}"}

            result = response.json()
            if result.get("ok"):
                structured_data = result.get("data")
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

    @classmethod
    def extract_lab_report_pipeline(cls, report, settings):
        """
        Calls the internal ai_service container (v1/extract-lab-report endpoint) using raw PDF file bytes.
        """
        try:
            report.report_file.seek(0)
            file_bytes = report.report_file.read()

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
                    report.save()
                    return {"ok": False, "error": result.get("error"), "report_id": report.id}
            else:
                report.save()
                return {"ok": False, "error": f"Cloud Service Error status {response.status_code}", "report_id": report.id}
        except Exception as e:
            logger.error(f"Error in extract_lab_report_pipeline: {str(e)}")
            report.save()
            return {"ok": False, "error": str(e), "report_id": report.id}

    @classmethod
    def render_pdf(cls, html_content, clinic):
        """
        Calls central ai_service Gotenberg PDF renderer endpoint.
        """
        api_url = "http://ai_service:8001/v1/render-pdf"
        headers = {
            "x-clinic-key": clinic.api_access_token if clinic else "",
            "Content-Type": "application/json"
        }
        payload = {
            "html": html_content
        }

        response = requests.post(api_url, json=payload, headers=headers, timeout=20)
        if response.status_code == 200:
            return response.content
        else:
            raise Exception(f"Gotenberg PDF Engine returned status {response.status_code}: {response.text}")
