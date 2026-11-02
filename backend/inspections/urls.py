"""
URL routing for the Inspections application.
"""

from django.urls import path
from inspections.views import (
    InspectionListView,
    InspectionDetailView,
    SingleInspectionView,
    BatchInspectionView,
    BatchStatusView,
    SupervisorReviewView,
    SupervisorInspectionListView
)

urlpatterns = [
    # Top-level inspections endpoint: GET ?product_id=... or POST single upload
    path('', InspectionListView.as_view(), name='inspection-list'),
    path('single/', SingleInspectionView.as_view(), name='inspection-single'),
    path('batch/', BatchInspectionView.as_view(), name='inspection-batch'),
    path('batch/<str:batch_id>/', BatchStatusView.as_view(), name='inspection-batch-status'),
    path('<int:pk>/', InspectionDetailView.as_view(), name='inspection-detail'),
    path('<int:pk>/review/', SupervisorReviewView.as_view(), name='inspection-review'),
]
