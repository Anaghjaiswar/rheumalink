from django.urls import path
from . import views

urlpatterns = [
    path("", views.clinic_home, name="clinic-home"),
    path("api/book-appointment/", views.book_appointment_api, name="api-book-appointment"),
]
