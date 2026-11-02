"""
URL routing for the Documents application.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from documents.views import (
    DocumentDownloadView,
    DocumentPagesView,
    DocumentViewSet,
)
from rag.views import (
    DocumentIndexTriggerView,
    DocumentIndexStatusView,
)

app_name = 'documents'

router = DefaultRouter()
router.register(r'', DocumentViewSet, basename='document')

urlpatterns = [
    path('<uuid:document_id>/pages/', DocumentPagesView.as_view(), name='document-pages'),
    path('<uuid:document_id>/download/', DocumentDownloadView.as_view(), name='document-download'),
    path('<uuid:document_id>/index/', DocumentIndexTriggerView.as_view(), name='document-index'),
    path('<uuid:document_id>/index-status/', DocumentIndexStatusView.as_view(), name='document-index-status'),
    path('', include(router.urls)),
]
