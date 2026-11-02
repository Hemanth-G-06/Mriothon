"""
Root views and health-check endpoints for the Manufacturing Manual Assistant.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """
    Health check API endpoint.

    Returns the operational status of the backend application.
    Independent of authentication and role permissions.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        payload = {
            "status": "healthy",
            "application": "Manufacturing Manual Assistant",
        }
        return Response(payload, status=status.HTTP_200_OK)

