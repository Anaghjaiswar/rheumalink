from django.urls import path
from .views import whatsapp_action_webhook

urlpatterns = [
    path('action-webhook/', whatsapp_action_webhook, name='whatsapp_webhook'),
]
