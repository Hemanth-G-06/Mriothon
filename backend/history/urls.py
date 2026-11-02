"""
URL routing for the History application.
Supports query history, supervisor metrics, audit provenance ledger, and escalations.
"""

from django.urls import path
from history.views import (
    AuditEventListView,
    AuditProvenanceDetailView,
    AuditProvenanceListView,
    EscalationListView,
    EscalationResolveView,
    QueryHistoryDetailView,
    QueryHistoryListView,
    SupervisorStatisticsView,
)

app_name = 'history'

urlpatterns = [
    # Base collection
    path('', QueryHistoryListView.as_view(), name='query-history-list'),
    path('statistics/', SupervisorStatisticsView.as_view(), name='supervisor-statistics'),
    path('audit/', AuditProvenanceListView.as_view(), name='audit-provenance-list'),
    path('audit/<str:request_id>/', AuditProvenanceDetailView.as_view(), name='audit-provenance-detail'),
    path('audit-events/', AuditEventListView.as_view(), name='audit-event-list'),
    path('escalations/', EscalationListView.as_view(), name='escalation-list'),
    path('escalations/<uuid:id>/resolve/', EscalationResolveView.as_view(), name='escalation-resolve'),
    path('<uuid:id>/', QueryHistoryDetailView.as_view(), name='query-history-detail'),

    # Supervisor nested compatibility
    path('history/', QueryHistoryListView.as_view(), name='supervisor-history-list'),
    path('history/<uuid:id>/', QueryHistoryDetailView.as_view(), name='supervisor-history-detail'),
    path('supervisor/escalations/', EscalationListView.as_view(), name='supervisor-escalations'),
    path('supervisor/escalations/<uuid:id>/resolve/', EscalationResolveView.as_view(), name='supervisor-escalations-resolve'),
]
