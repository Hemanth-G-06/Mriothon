"""
Views and API endpoints for the Machines application.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsAdminOrReadOnly
from machines.models import Machine
from machines.serializers import MachineSerializer


class MachineViewSet(viewsets.ModelViewSet):
    """
    CRUD viewset for Machine assets.
    - Any authenticated user (Admin, Engineer, Supervisor) can list and view machines.
    - Only Admins can register, update, or delete machine assets.
    """
    queryset = Machine.objects.all()
    serializer_class = MachineSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None  # Return unpaginated list directly for clean frontend consumption
