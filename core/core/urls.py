from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView
from user.serializers import CustomTokenObtainPairView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include('user.urls')),
    path('', include('clinic.urls')),
    path('', include('treatment.urls')),
    path('whatsapp/', include('whatsapp.urls')),
    path('notifications/', include('notification.urls')),
]
