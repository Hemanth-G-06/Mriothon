"""
URL routing for Authentication and User Management.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import (
    CurrentUserView,
    LoginView,
    LogoutView,
    RefreshTokenView,
    RegisterView,
    UserViewSet,
)

app_name = 'accounts'

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='token_refresh'),
    path('auth/me/', CurrentUserView.as_view(), name='current_user'),
    path('auth/profile/', CurrentUserView.as_view(), name='profile'),

    # User management endpoints (/api/users/, /api/users/{id}/)
    path('', include(router.urls)),
]
