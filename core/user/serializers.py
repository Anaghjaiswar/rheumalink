from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Minimal JWT Token Serializer embedding strictly user_id and role in JWT payload.
    Returns user details (id, role, full_name) in login response JSON.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        full_name = getattr(self.user, 'get_full_name', lambda: f"{self.user.first_name} {self.user.last_name}".strip())() or self.user.email
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'role': self.user.role,
            'full_name': full_name,
        }
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Custom token refresh serializer ensuring role is persisted in new access token payload,
    and returns refreshed user profile details.
    """
    def validate(self, attrs):
        data = super().validate(attrs)
        refresh = RefreshToken(attrs['refresh'])
        user_id = refresh.payload.get('user_id')

        if user_id:
            from user.models import User
            try:
                user = User.objects.get(id=user_id)
                full_name = getattr(user, 'get_full_name', lambda: f"{user.first_name} {user.last_name}".strip())() or user.email
                data['user'] = {
                    'id': user.id,
                    'email': user.email,
                    'role': user.role,
                    'full_name': full_name,
                }
            except User.DoesNotExist:
                pass
        return data


class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer

