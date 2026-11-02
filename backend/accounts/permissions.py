"""
Custom Role-Based Access Control (RBAC) permission classes.
"""

from rest_framework import permissions
from accounts.models import UserRole


class BaseRolePermission(permissions.BasePermission):
    """
    Base permission class ensuring user is authenticated, active, and valid.
    """

    def is_valid_user(self, request):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_active
        )


class IsAdmin(BaseRolePermission):
    """
    Allows access only to authenticated users with the Administrator role
    or Django superuser privileges.
    """

    def has_permission(self, request, view):
        if not self.is_valid_user(request):
            return False
        return request.user.role == UserRole.ADMIN or request.user.is_superuser


class IsEngineer(BaseRolePermission):
    """
    Allows access only to authenticated users with the Engineer role.
    """

    def has_permission(self, request, view):
        if not self.is_valid_user(request):
            return False
        return request.user.role == UserRole.ENGINEER


class IsSupervisor(BaseRolePermission):
    """
    Allows access only to authenticated users with the Supervisor role.
    """

    def has_permission(self, request, view):
        if not self.is_valid_user(request):
            return False
        return request.user.role == UserRole.SUPERVISOR


class IsAdminOrReadOnly(BaseRolePermission):
    """
    Allows read-only access to any authenticated user, but restricts
    write/mutation operations strictly to Administrators.
    """

    def has_permission(self, request, view):
        if not self.is_valid_user(request):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.role == UserRole.ADMIN or request.user.is_superuser
