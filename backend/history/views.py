"""
Views and API endpoints for History, Audit Provenance, Supervisor Escalations,
and TrustOps monitoring.
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404

from accounts.models import UserRole
from history.models import (
    AuditEvent,
    AuditProvenanceRecord,
    Citation,
    Escalation,
    EscalationStatus,
    QueryRecord,
)
from history.serializers import (
    AuditEventSerializer,
    AuditProvenanceRecordSerializer,
    CitationSerializer,
    EscalationSerializer,
    QueryRecordSerializer,
)
from machines.models import Machine


class IsActiveAuthenticatedUser(permissions.BasePermission):
    """
    Enforces that the user is authenticated and active.
    Rejects inactive or deactivated accounts with HTTP 403.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_active
        )


class IsSupervisorOrAdmin(permissions.BasePermission):
    """
    Restricts access to Supervisors and Administrators only.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            request.user.role in (UserRole.ADMIN, UserRole.SUPERVISOR)
        )


class QueryHistoryListView(generics.ListAPIView):
    """
    GET /api/history/ or /api/supervisor/history/
    Lists query records based on user role:
    - Engineers: Restricted strictly to their own queries.
    - Supervisors & Admins: Permitted to inspect all query records with search and filter capabilities.
    """
    serializer_class = QueryRecordSerializer
    permission_classes = [IsActiveAuthenticatedUser]

    def get_queryset(self):
        user = self.request.user
        qs = QueryRecord.objects.select_related('user', 'machine').all()

        if user.role == UserRole.ENGINEER:
            qs = qs.filter(user=user)

        machine_id = self.request.query_params.get('machine_id') or self.request.query_params.get('machine')
        if machine_id:
            try:
                qs = qs.filter(machine_id=machine_id)
            except Exception:
                qs = qs.filter(machine__name__icontains=machine_id)

        user_id = self.request.query_params.get('user_id')
        if user_id and user.role in (UserRole.ADMIN, UserRole.SUPERVISOR):
            qs = qs.filter(user_id=user_id)

        engineer_filter = self.request.query_params.get('engineer', '').strip()
        if engineer_filter and user.role in (UserRole.ADMIN, UserRole.SUPERVISOR):
            qs = qs.filter(
                Q(user__email__icontains=engineer_filter) |
                Q(user__first_name__icontains=engineer_filter) |
                Q(user__last_name__icontains=engineer_filter)
            )

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(question__icontains=search) |
                Q(answer__icontains=search) |
                Q(machine__name__icontains=search)
            )

        status_filter = self.request.query_params.get('status', '').strip().lower()
        if status_filter in ('answered',):
            qs = qs.filter(abstained=False)
        elif status_filter in ('insufficient_evidence', 'abstained'):
            qs = qs.filter(abstained=True)

        date_filter = self.request.query_params.get('date', '').strip()
        if date_filter:
            qs = qs.filter(created_at__date=date_filter)

        return qs.order_by('-created_at')


class QueryHistoryDetailView(generics.RetrieveAPIView):
    """
    GET /api/history/{id}/
    Retrieves a single query record if authorized:
    - Engineers can only retrieve their own record (others return 404).
    - Supervisors and Admins can retrieve any record.
    """
    serializer_class = QueryRecordSerializer
    permission_classes = [IsActiveAuthenticatedUser]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.ENGINEER:
            return QueryRecord.objects.select_related('user', 'machine').filter(user=user)
        return QueryRecord.objects.select_related('user', 'machine').all()


class SupervisorStatisticsView(APIView):
    """
    GET /api/history/statistics/ or /api/supervisor/statistics/
    Aggregates operational metrics for supervisor overview.
    """
    permission_classes = [IsActiveAuthenticatedUser]

    def get(self, request, *args, **kwargs):
        total_questions = QueryRecord.objects.count()
        insufficient = QueryRecord.objects.filter(abstained=True).count()
        answered = total_questions - insufficient
        active_machines = Machine.objects.count()
        escalations_pending = Escalation.objects.filter(status=EscalationStatus.PENDING).count()

        return Response({
            'total_questions': total_questions,
            'answered_questions': answered,
            'insufficient_evidence_questions': insufficient,
            'pending_escalations': escalations_pending,
            'active_machines_monitored': active_machines
        }, status=status.HTTP_200_OK)


class AuditProvenanceListView(generics.ListAPIView):
    """
    GET /api/history/audit/
    Lists tamper-resistant execution provenance records for AgentOps auditing.
    Supervisors and Admins only.
    """
    serializer_class = AuditProvenanceRecordSerializer
    permission_classes = [IsSupervisorOrAdmin]

    def get_queryset(self):
        qs = AuditProvenanceRecord.objects.select_related('machine', 'user').all()
        machine_id = self.request.query_params.get('machine_id')
        if machine_id:
            qs = qs.filter(machine_id=machine_id)
        outcome = self.request.query_params.get('outcome')
        if outcome:
            qs = qs.filter(evidence_evaluation_outcome=outcome.upper())
        return qs.order_by('-created_at')


class AuditProvenanceDetailView(generics.RetrieveAPIView):
    """
    GET /api/history/audit/{request_id}/
    Retrieves complete AgentOps execution trace, intermediate transitions, and chunk metadata.
    """
    serializer_class = AuditProvenanceRecordSerializer
    permission_classes = [IsSupervisorOrAdmin]
    lookup_field = 'request_id'

    def get_queryset(self):
        return AuditProvenanceRecord.objects.select_related('machine', 'user').all()


class EscalationListView(generics.ListAPIView):
    """
    GET /api/history/escalations/ or /api/supervisor/escalations/
    Lists inquiries flagged for supervisor review.
    """
    serializer_class = EscalationSerializer
    permission_classes = [IsSupervisorOrAdmin]

    def get_queryset(self):
        qs = Escalation.objects.select_related('machine', 'engineer', 'query').all()
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param.upper())
        return qs.order_by('-created_at')


class EscalationResolveView(APIView):
    """
    POST /api/history/escalations/{id}/resolve/
    Resolves or closes a supervisor escalation.
    """
    permission_classes = [IsSupervisorOrAdmin]

    def post(self, request, id):
        escalation = get_object_or_404(Escalation, pk=id)
        resolution_notes = request.data.get('resolution_notes', '').strip()
        new_status = request.data.get('status', EscalationStatus.RESOLVED)

        if new_status not in (EscalationStatus.RESOLVED, EscalationStatus.REJECTED):
            new_status = EscalationStatus.RESOLVED

        escalation.status = new_status
        escalation.resolution_notes = resolution_notes
        escalation.resolved_by = request.user
        escalation.resolved_at = timezone.now()
        escalation.save(update_fields=['status', 'resolution_notes', 'resolved_by', 'resolved_at'])

        return Response(EscalationSerializer(escalation).data, status=status.HTTP_200_OK)


class AuditEventListView(generics.ListAPIView):
    """
    GET /api/history/audit-events/
    Lists security events such as blocked cross-machine access.
    """
    serializer_class = AuditEventSerializer
    permission_classes = [IsSupervisorOrAdmin]

    def get_queryset(self):
        return AuditEvent.objects.select_related('machine', 'user').all().order_by('-timestamp')
