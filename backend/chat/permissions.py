"""
Permission classes for Engineer Conversational Chatbot.
Restricts access exclusively to authenticated users with the ENGINEER role.
Admin and Supervisor accounts are explicitly denied access.
"""

from rest_framework import permissions
from accounts.models import UserRole


class IsEngineerUser(permissions.BasePermission):
    """
    Grants access exclusively to authenticated, active Engineer users.
    Denies access to Administrators, Supervisors, and anonymous users with HTTP 403.
    """
    message = "Only Engineers are authorized to access the conversational manual assistant."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        return request.user.role == UserRole.ENGINEER

