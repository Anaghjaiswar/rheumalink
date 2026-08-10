from django.urls import path
from .compounder_api import get_compounder_dashboard_api, register_patient_api, create_appointment_api
from .doctor_api import get_doctor_dashboard_api, save_consultation_api
from .joint_chart_api import get_joint_chart_api, save_joint_chart_api
from .rumat_api import get_rumat_diagnosis_api, save_rumat_diagnosis_api
from .vitals_api import get_appointment_vitals_api, capture_vitals_api
from .medical_info_api import get_patient_medical_info_api, save_patient_medical_info_api
from .diagnosis_api import save_diagnosis_api, das28_score_api
from .autosuggest_api import medicine_autosuggest_api, labtest_autosuggest_api
from .prescription_api import download_prescription_pdf_api, send_prescription_whatsapp_api
from .clinic_api import get_clinic_settings_api

urlpatterns = [
    # Clinic Settings API (Public & Cached)
    path("v1/clinic/settings/", get_clinic_settings_api, name="api-v1-clinic-settings"),

    # Compounder Desk API Endpoints
    path("v1/compounder/dashboard/", get_compounder_dashboard_api, name="api-v1-compounder-dashboard"),
    path("v1/compounder/patient/register/", register_patient_api, name="api-v1-compounder-register"),
    path("v1/compounder/appointment/create/", create_appointment_api, name="api-v1-compounder-create-appointment"),

    # Doctor Desk API Endpoints
    path("v1/doctor/dashboard/", get_doctor_dashboard_api, name="api-v1-doctor-dashboard"),
    path("v1/doctor/consultation/<int:appointment_id>/save/", save_consultation_api, name="api-v1-doctor-consultation-save"),
    path("v1/doctor/diagnosis/<int:appointment_id>/save/", save_diagnosis_api, name="api-v1-doctor-diagnosis-save"),

    # Joint Assessment Chart API Endpoints
    path("v1/joint-chart/<int:appointment_id>/", get_joint_chart_api, name="api-v1-joint-chart-get"),
    path("v1/joint-chart/<int:appointment_id>/save/", save_joint_chart_api, name="api-v1-joint-chart-save"),

    # Rheumat Diagnosis & Symptoms Book API Endpoints
    path("v1/rumat-diagnosis/<int:appointment_id>/", get_rumat_diagnosis_api, name="api-v1-rumat-diagnosis-get"),
    path("v1/rumat-diagnosis/<int:appointment_id>/save/", save_rumat_diagnosis_api, name="api-v1-rumat-diagnosis-save"),

    # Vitals & Medical Info API Endpoints
    path("v1/vitals/<int:appointment_id>/", get_appointment_vitals_api, name="api-v1-vitals-get"),
    path("v1/vitals/<int:appointment_id>/save/", capture_vitals_api, name="api-v1-vitals-save"),
    path("v1/medical-info/<int:patient_id>/", get_patient_medical_info_api, name="api-v1-medical-info-get"),
    path("v1/medical-info/<int:patient_id>/save/", save_patient_medical_info_api, name="api-v1-medical-info-save"),

    # Analytics & Autocomplete APIs
    path("v1/das28/<int:appointment_id>/", das28_score_api, name="api-v1-das28-score"),
    path("v1/autosuggest/medicine/", medicine_autosuggest_api, name="api-v1-autosuggest-medicine"),
    path("v1/autosuggest/labtest/", labtest_autosuggest_api, name="api-v1-autosuggest-labtest"),

    # Prescription PDF & WhatsApp APIs
    path("v1/prescription/<int:prescription_id>/pdf/", download_prescription_pdf_api, name="api-v1-prescription-pdf"),
    path("v1/prescription/<int:prescription_id>/send/", send_prescription_whatsapp_api, name="api-v1-prescription-send"),
]
