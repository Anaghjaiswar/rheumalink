from django.urls import re_path

from treatment.consumers import DoctorQueueConsumer

websocket_urlpatterns = [
    re_path(r"ws/doctor-queue/$", DoctorQueueConsumer.as_asgi()),
    re_path(r"ws/doctor-queue/(?P<doctor_id>\d+)/$", DoctorQueueConsumer.as_asgi()),
]
