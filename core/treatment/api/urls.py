from django.urls import path
from .compounder_api import get_compounder_dashboard_api, register_patient_api, create_appointment_api
from .doctor_api import get_doctor_dashboard_api, save_consultation_api
from .joint_chart_api import get_joint_chart_api, save_joint_chart_api
from .rumat_api import get_rumat_diagnosis_api, save_rumat_diagnosis_api

urlpatterns = [
    # Compounder Desk API Endpoints
    path("v1/compounder/dashboard/", get_compounder_dashboard_api, name="api-v1-compounder-dashboard"),
    path("v1/compounder/patient/register/", register_patient_api, name="api-v1-compounder-register"),
    path("v1/compounder/appointment/create/", create_appointment_api, name="api-v1-compounder-create-appointment"),

    # Doctor Desk API Endpoints
    path("v1/doctor/dashboard/", get_doctor_dashboard_api, name="api-v1-doctor-dashboard"),
    path("v1/doctor/consultation/<int:appointment_id>/save/", save_consultation_api, name="api-v1-doctor-consultation-save"),

    # Joint Assessment Chart API Endpoints
    path("v1/joint-chart/<int:appointment_id>/", get_joint_chart_api, name="api-v1-joint-chart-get"),
    path("v1/joint-chart/<int:appointment_id>/save/", save_joint_chart_api, name="api-v1-joint-chart-save"),

    # Rheumat Diagnosis & Symptoms Book API Endpoints
    path("v1/rumat-diagnosis/<int:appointment_id>/", get_rumat_diagnosis_api, name="api-v1-rumat-diagnosis-get"),
    path("v1/rumat-diagnosis/<int:appointment_id>/save/", save_rumat_diagnosis_api, name="api-v1-rumat-diagnosis-save"),
]
