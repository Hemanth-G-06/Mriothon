"""
Authentication and User Management views.
"""

from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.models import User, UserRole
from accounts.permissions import IsAdmin
from accounts.serializers import (
    CustomTokenObtainPairSerializer,
    UserAdminCreateSerializer,
    UserAdminUpdateSerializer,
    UserProfileSerializer,
)


class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Authenticates a user via email and password.
    Returns JWT access and refresh tokens plus basic user profile information.
    """
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


class RefreshTokenView(TokenRefreshView):
    """
    POST /api/auth/refresh/
    Exchanges a valid refresh token for a new access token.
    Follows configured token rotation policy.
    """
    permission_classes = [AllowAny]


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Terminates the user's JWT session by blacklisting the submitted refresh token.
    Permits unauthenticated requests so logout succeeds even if the access token has expired.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken
                from rest_framework_simplejwt.exceptions import TokenError
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                # Token may already be blacklisted or invalid; proceed with clean logout
                pass
        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """
    GET /api/auth/me/
    Retrieves the currently authenticated user's profile.
    Requires a valid JWT Bearer token.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """
    Administrator-only User Management ViewSet:
    - GET /api/users/ (List users)
    - POST /api/users/ (Create user)
    - GET /api/users/{id}/ (Retrieve user)
    - PATCH /api/users/{id}/ (Partial update user)
    - DELETE /api/users/{id}/ (Safe deactivation)
    """
    permission_classes = [IsAdmin]
    queryset = User.objects.all().order_by('-date_joined')

    def get_serializer_class(self):
        if self.action == 'create':
            return UserAdminCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserAdminUpdateSerializer
        return UserProfileSerializer

    def destroy(self, request, *args, **kwargs):
        """
        Soft-delete implementation: deactivates user (is_active=False)
        rather than physically removing records from the database.
        Guards against deactivating the last active Administrator.
        """
        user = self.get_object()

        # Guard against deactivating the last active Administrator
        if user.role == UserRole.ADMIN and user.is_active:
            other_active_admins = User.objects.filter(
                role=UserRole.ADMIN,
                is_active=True
            ).exclude(pk=user.pk)

            if not other_active_admins.exists():
                return Response(
                    {"detail": "Cannot deactivate the last active Administrator."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        user.is_active = False
        user.save(update_fields=['is_active'])

        return Response(
            {
                "detail": "User account successfully deactivated.",
                "id": user.id,
                "email": user.email,
                "is_active": user.is_active,
            },
            status=status.HTTP_200_OK
        )
