"""
URL routing for the Documents application.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from documents.views import (
    DocumentDownloadView,
    DocumentPagesView,
    DocumentViewerView,
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
    path('<uuid:document_id>/pdf/', DocumentViewerView.as_view(), name='document-pdf'),
    path('<uuid:document_id>/view/', DocumentViewerView.as_view(), name='document-view'),
    path('<uuid:document_id>/index/', DocumentIndexTriggerView.as_view(), name='document-index'),
    path('<uuid:document_id>/index-status/', DocumentIndexStatusView.as_view(), name='document-index-status'),
    path('upload/', DocumentViewSet.as_view({'post': 'create'}), name='document-upload-alias'),
    path('', include(router.urls)),
]
