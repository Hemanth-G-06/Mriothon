"""
URL routing for the History application.
Supports both /api/supervisor/ and /api/history/ hierarchies.
"""

from django.urls import path
from history.views import (
    SupervisorHistoryListView,
    SupervisorHistoryDetailView,
    SupervisorStatisticsView,
)

urlpatterns = [
    # Top-level paths (e.g. /api/history/ or /api/supervisor/)
    path('', SupervisorHistoryListView.as_view(), name='history-list'),
    path('statistics/', SupervisorStatisticsView.as_view(), name='history-statistics'),
    path('<int:pk>/', SupervisorHistoryDetailView.as_view(), name='history-detail'),

    # Nested supervisor paths (when included under /api/supervisor/)
    path('history/', SupervisorHistoryListView.as_view(), name='supervisor-history-list'),
    path('history/<int:pk>/', SupervisorHistoryDetailView.as_view(), name='supervisor-history-detail'),
]
