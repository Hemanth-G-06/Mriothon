"""
Views and API endpoints for the History application.
"""

from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from history.models import QueryRecord
from history.serializers import QueryRecordSerializer
from machines.models import Machine


class SupervisorHistoryListView(APIView):
    """
    GET /api/supervisor/history/ (also /api/history/)
    Retrieves past question-and-answer interactions with audit trail filters.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        queryset = QueryRecord.objects.select_related('machine', 'user').all()

        search = request.query_params.get('search', '').strip()
        machine_filter = request.query_params.get('machine', '').strip()
        engineer_filter = request.query_params.get('engineer', '').strip()
        date_filter = request.query_params.get('date', '').strip()
        status_filter = request.query_params.get('status', '').strip().lower()

        if search:
            queryset = queryset.filter(
                Q(question__icontains=search) |
                Q(answer__icontains=search) |
                Q(machine__name__icontains=search) |
                Q(engineer_name__icontains=search)
            )

        if machine_filter:
            if machine_filter.isdigit():
                queryset = queryset.filter(machine_id=int(machine_filter))
            else:
                queryset = queryset.filter(machine__name__icontains=machine_filter)

        if engineer_filter:
            queryset = queryset.filter(
                Q(engineer_name__icontains=engineer_filter) |
                Q(user__email__icontains=engineer_filter)
            )

        if date_filter:
            queryset = queryset.filter(created_at__date=date_filter)

        if status_filter == 'answered':
            queryset = queryset.filter(is_insufficient_evidence=False)
        elif status_filter == 'insufficient_evidence':
            queryset = queryset.filter(is_insufficient_evidence=True)

        serializer = QueryRecordSerializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'total': queryset.count()
        }, status=status.HTTP_200_OK)


class SupervisorHistoryDetailView(APIView):
    """
    GET /api/supervisor/history/<int:pk>/ (also /api/history/<int:pk>/)
    Retrieves full details for a single QA audit inquiry.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        try:
            record = QueryRecord.objects.select_related('machine', 'user').get(pk=pk)
        except QueryRecord.DoesNotExist:
            return Response({'detail': 'Audit record not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = QueryRecordSerializer(record)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SupervisorStatisticsView(APIView):
    """
    GET /api/supervisor/statistics/ (also /api/history/statistics/)
    Aggregates operational metrics for supervisor overview.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        total_questions = QueryRecord.objects.count()
        insufficient = QueryRecord.objects.filter(is_insufficient_evidence=True).count()
        answered = total_questions - insufficient
        active_machines = Machine.objects.count()

        return Response({
            'total_questions': total_questions,
            'answered_questions': answered,
            'insufficient_evidence_questions': insufficient,
            'active_machines_monitored': active_machines
        }, status=status.HTTP_200_OK)
