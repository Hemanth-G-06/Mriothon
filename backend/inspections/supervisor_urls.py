"""
URL routing for Supervisor Inspection review endpoints (/api/supervisor/inspections/).
"""

from django.urls import path
from inspections.views import SupervisorInspectionListView, SupervisorReviewView

urlpatterns = [
    path('', SupervisorInspectionListView.as_view(), name='supervisor-inspection-list'),
    path('<int:pk>/review/', SupervisorReviewView.as_view(), name='supervisor-inspection-review'),
]

