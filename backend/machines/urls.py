"""
URL routing for the Machines application.
"""

from rest_framework.routers import DefaultRouter
from machines.views import MachineViewSet
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from machines.views import (
    MachineAssignmentDeleteView,
    MachineAssignmentListCreateView,
    MachineViewSet,
)
from documents.views import MachineDocumentsListView

app_name = 'machines'

router = DefaultRouter()
router.register(r'', MachineViewSet, basename='machine')

urlpatterns = router.urls

urlpatterns = [
    # Machine documents listing
    path('<uuid:machine_id>/documents/', MachineDocumentsListView.as_view(), name='machine-documents'),

    # Machine assignments endpoints
    path('<uuid:machine_id>/assignments/', MachineAssignmentListCreateView.as_view(), name='machine-assignments'),
    path('<uuid:machine_id>/assignments/<int:assignment_id>/', MachineAssignmentDeleteView.as_view(), name='machine-unassign'),

    # Machine CRUD routes (via router)
    path('', include(router.urls)),
]
