import logging
from django.db import transaction
from rag.services.chroma_service import ChromaService
logger = logging.getLogger(__name__)
"""
Views and API endpoints for Machine Management and Engineer Assignments.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User, UserRole
from accounts.permissions import IsAdmin
from machines.models import Machine, MachineAssignment, MachineStatus
from machines.permissions import CanAccessMachineObject, IsAdminOrReadOnly
from machines.serializers import (
    MachineAssignmentCreateSerializer,
    MachineAssignmentSerializer,
    MachineCreateSerializer,
    MachineDetailSerializer,
    MachineListSerializer,
    MachineUpdateSerializer,
)
from machines.services import (
    assign_engineer_to_machine,
    can_user_access_machine,
    get_accessible_machines_queryset,
    unassign_engineer_from_machine,
)


class MachineViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Machines:
    - GET /api/machines/ (Admins/Supervisors see all; Engineers see assigned active machines)
    - POST /api/machines/ (Administrator only)
    - GET /api/machines/{id}/ (Admins/Supervisors see all; Engineers see if assigned)
    - PATCH /api/machines/{id}/ (Administrator only; machine_code is immutable)
    - DELETE /api/machines/{id}/ (Administrator only; soft deactivation)
    - GET /api/machines/assigned/ (Explicit list of assigned machines for current engineer)
    """
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, CanAccessMachineObject]

    def get_queryset(self):
        return get_accessible_machines_queryset(self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return MachineCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return MachineUpdateSerializer
        elif self.action == 'retrieve':
            return MachineDetailSerializer
        return MachineListSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """
        Deletes or deactivates a machine.
        - Admin only.
        - If ?permanent=true (or default delete action):
          Cleans up ChromaDB vectors for all associated documents and the machine,
          removes physical PDF files, and safely cascades relational records.
        - If ?permanent=false:
          Soft-deactivates the machine (sets status to INACTIVE).
        """
        if request.user.role != UserRole.ADMIN and not request.user.is_superuser:
            raise PermissionDenied("Only Administrators can delete or deactivate machines.")

        machine = self.get_object()
        permanent = request.query_params.get('permanent', 'false').lower() in ['true', '1']

        if not permanent:
            machine.status = MachineStatus.INACTIVE
            machine.save(update_fields=['status', 'updated_at'])
            return Response(
                {
                    "detail": "Machine successfully deactivated.",
                    "id": str(machine.id),
                    "machine_code": machine.machine_code,
                    "status": machine.status,
                    "deleted": False,
                },
                status=status.HTTP_200_OK
            )

        # Permanent deletion workflow
        docs = list(machine.documents.all())
        from django.conf import settings as _settings
        if getattr(_settings, 'VECTOR_BACKEND', 'pgvector') == 'chroma':
            chroma_service = ChromaService()
            # 1. Clean up ChromaDB vectors for each associated document
            for doc in docs:
                try:
                    chroma_service.delete_document_vectors(str(doc.id))
                except Exception as exc:
                    logger.warning("Error deleting ChromaDB vectors for document %s: %s", doc.id, exc)

            # 2. Clean up any remaining machine-level ChromaDB vectors
            try:
                chroma_service.delete_machine_vectors(str(machine.id))
            except Exception as exc:
                logger.warning("Error deleting ChromaDB machine vectors for %s: %s", machine.id, exc)

        # 3. Clean up physical PDF files from storage
        for doc in docs:
            try:
                if doc.file:
                    doc.file.delete(save=False)
            except Exception as exc:
                logger.warning("Error deleting PDF file for document %s: %s", doc.id, exc)

        # 4. Atomic relational cascade deletion
        machine_code = machine.machine_code
        machine_id_str = str(machine.id)
        with transaction.atomic():
            machine.delete()

        return Response(
            {
                "detail": f"Machine '{machine_code}' and associated documents/vectors successfully deleted.",
                "id": machine_id_str,
                "machine_code": machine_code,
                "deleted": True,
            },
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='assigned')
    def assigned(self, request):
        """
        Convenience endpoint for authenticated engineers to list their assigned machines.
        """
        if request.user.role == UserRole.ENGINEER:
            assigned_machines = Machine.objects.filter(
                assignments__user=request.user,
                assignments__is_active=True,
                status=MachineStatus.ACTIVE
            ).distinct()
        elif request.user.role in [UserRole.ADMIN, UserRole.SUPERVISOR] or request.user.is_superuser:
            assigned_machines = Machine.objects.filter(status=MachineStatus.ACTIVE)
        else:
            assigned_machines = Machine.objects.none()

        serializer = MachineListSerializer(assigned_machines, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MachineAssignmentListCreateView(APIView):
    """
    Endpoint for managing engineer assignments to a machine:
    - GET /api/machines/{id}/assignments/ (View assignments according to RBAC policy)
    - POST /api/machines/{id}/assignments/ (Administrator only: assign an engineer)
    """
    permission_classes = [IsAuthenticated]

    def get_machine(self, machine_id):
        return get_object_or_404(Machine, pk=machine_id)

    def get(self, request, machine_id):
        machine = self.get_machine(machine_id)

        # Enforce access policy
        if request.user.role in [UserRole.ADMIN, UserRole.SUPERVISOR] or request.user.is_superuser:
            assignments = machine.assignments.all()
        elif request.user.role == UserRole.ENGINEER:
            if not can_user_access_machine(request.user, machine):
                raise PermissionDenied("You do not have permission to view assignments for this machine.")
            assignments = machine.assignments.filter(user=request.user, is_active=True)
        else:
            raise PermissionDenied("You do not have permission to view machine assignments.")

        serializer = MachineAssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, machine_id):
        # Only Administrator can assign engineers
        if request.user.role != UserRole.ADMIN and not request.user.is_superuser:
            raise PermissionDenied("Only Administrators can assign engineers to machines.")

        machine = self.get_machine(machine_id)
        input_serializer = MachineAssignmentCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        target_user = User.objects.get(pk=input_serializer.validated_data['user_id'])

        try:
            assignment = assign_engineer_to_machine(
                machine=machine,
                engineer_user=target_user,
                assigned_by_user=request.user
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            raise DRFValidationError(detail)

        output_serializer = MachineAssignmentSerializer(assignment)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class MachineAssignmentDeleteView(APIView):
    """
    Endpoint for unassigning an engineer from a machine:
    - DELETE /api/machines/{id}/assignments/{assignment_id}/ (Administrator only)
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, machine_id, assignment_id):
        machine = get_object_or_404(Machine, pk=machine_id)

        try:
            assignment = unassign_engineer_from_machine(machine, assignment_id)
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            raise DRFValidationError(detail)

        return Response(
            {
                "detail": "Engineer successfully unassigned from machine.",
                "assignment_id": assignment.id,
                "is_active": assignment.is_active,
            },
            status=status.HTTP_200_OK
        )
