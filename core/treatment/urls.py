from django.urls import path

from . import views

urlpatterns = [
    path("", views.compounder_dashboard, name="compounder-dashboard"),
    path("compounder-dashboard/", views.compounder_dashboard, name="compounder-dashboard"),
    path("doctor-dashboard/", views.doctor_dashboard, name="doctor-dashboard"),
    path("doctor/joint-chart/<int:appointment_id>/", views.joint_chart_page, name="joint-chart-page"),
    path("api/queue/", views.queue_data, name="queue-data"),
    path("api/medicine-autosuggest/", views.medicine_autosuggest, name="medicine-autosuggest"),
    path("api/das28/<int:appointment_id>/", views.das28_score, name="das28-score"),
    path("api/patient-medical-info/<int:patient_id>/", views.get_patient_medical_info, name="patient-medical-info"),
]
