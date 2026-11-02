"""
URL routing for the Documents application.
"""

from rest_framework.routers import DefaultRouter
from documents.views import DocumentViewSet

app_name = 'documents'

router = DefaultRouter()
router.register(r'', DocumentViewSet, basename='document')

urlpatterns = router.urls
