from django.urls import path
from . import views

urlpatterns = [
    path('api/list/', views.list_notifications_api, name='api-notifications-list'),
    path('api/<int:pk>/read/', views.mark_notification_read_api, name='api-notifications-read'),
]
