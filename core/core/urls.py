from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('treatment.urls')),
    path('whatsapp/', include('whatsapp.urls')),
]
