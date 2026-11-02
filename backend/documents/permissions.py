"""
Permission classes for Document Management.
Enforces role-based document access and machine-level authorization.
"""

from rest_framework import permissions
from accounts.models import UserRole
from documents.services import can_user_access_document


class IsAdminUserOrReadOnly(permissions.BasePermission):
    """
    Grants mutation permissions (POST, DELETE) strictly to Administrators.
    Grants read permissions (GET, HEAD, OPTIONS) to authenticated active users.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.role == UserRole.ADMIN or request.user.is_superuser


class CanAccessDocumentObject(permissions.BasePermission):
    """
    Object-level permission evaluating whether the user is authorized
    to view, inspect, or download a specific Document.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
            return False

        # Mutations require Administrator
        if request.method not in permissions.SAFE_METHODS:
            return request.user.role == UserRole.ADMIN or request.user.is_superuser

        # Read operations delegate to centralized service
        return can_user_access_document(request.user, obj)

