from django.urls import path

from . import views

urlpatterns = [
    path("", views.compounder_dashboard, name="compounder-dashboard"),
    path("compounder-dashboard/", views.compounder_dashboard, name="compounder-dashboard"),
    path("doctor-dashboard/", views.doctor_dashboard, name="doctor-dashboard"),
    path("doctor/joint-chart/<int:appointment_id>/", views.joint_chart_page, name="joint-chart-page"),
    path("doctor/rumat-diagnosis/<int:appointment_id>/", views.rumat_diagnosis_page, name="rumat-diagnosis-page"),
    path("api/queue/", views.queue_data, name="queue-data"),
    path("api/medicine-autosuggest/", views.medicine_autosuggest, name="medicine-autosuggest"),
    path("api/labtest-autosuggest/", views.labtest_autosuggest, name="labtest-autosuggest"),
    path("api/das28/<int:appointment_id>/", views.das28_score, name="das28-score"),
    path("api/patient-medical-info/<int:patient_id>/", views.get_patient_medical_info, name="patient-medical-info"),
    path("api/patient-vitals/<int:appointment_id>/", views.get_appointment_vitals, name="patient-vitals"),
    path("api/generate-rumat-summary/<int:appointment_id>/", views.generate_rumat_summary, name="generate-rumat-summary"),
    path("api/diagnosis-status/<int:appointment_id>/", views.get_diagnosis_status, name="diagnosis-status"),
    path("api/proxy-correct-transcription/", views.proxy_correct_transcription, name="proxy-correct-transcription"),
    path("api/proxy-structure-clinical-note/", views.proxy_structure_clinical_note, name="proxy-structure-clinical-note"),
    path("api/prescription/<int:prescription_id>/pdf/", views.download_prescription_pdf, name="download-prescription-pdf"),
    path("api/prescription/<int:prescription_id>/preview/", views.prescription_preview, name="prescription-preview"),
    path("api/prescription/<int:prescription_id>/send/", views.send_prescription_to_patient, name="send-prescription-to-patient"),
    path("upload-lab-report/", views.upload_lab_report_page, name="upload-lab-report-page"),
    path("api/lab-report/upload-temp/", views.api_upload_lab_report_temp, name="api-upload-lab-report-temp"),
    path("api/lab-report/task-status/<str:task_id>/", views.api_lab_report_task_status, name="api-lab-report-task-status"),
    path("api/lab-report/save/<int:report_id>/", views.api_save_extracted_lab_data, name="api-save-extracted-lab-data"),
    path("api/patient/<int:patient_id>/appointments/", views.api_patient_appointments, name="api-patient-appointments"),
    path("api/patient/search/", views.api_patient_search, name="api-patient-search"),
]
