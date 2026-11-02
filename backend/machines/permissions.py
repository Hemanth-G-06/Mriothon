"""
Permission classes for Machine Management.
Enforces the role-based access policy on machines and machine assignments.
"""

from rest_framework import permissions
from accounts.models import UserRole
from machines.services import can_user_access_machine


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Grants write/mutation permissions strictly to Administrators.
    Grants read permissions to all authenticated, active users.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.role == UserRole.ADMIN or request.user.is_superuser


class CanAccessMachineObject(permissions.BasePermission):
    """
    Object-level permission evaluating whether the user can access a specific Machine instance.
    - Admin: All access.
    - Supervisor: Read-only access to all machines.
    - Engineer: Read-only access to assigned active machines only.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
            return False

        # Mutation operations strictly require Administrator role
        if request.method not in permissions.SAFE_METHODS:
            return request.user.role == UserRole.ADMIN or request.user.is_superuser

        # Read operations use centralized access service
        return can_user_access_machine(request.user, obj)

