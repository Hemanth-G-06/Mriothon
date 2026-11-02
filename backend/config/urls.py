"""
URL configuration for the Manufacturing Manual Assistant project.

Root API URL routing mapping to domain applications and system endpoints.
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from config.views import HealthCheckView
from inspections.views import SupervisorInspectionListView, SupervisorReviewView

urlpatterns = [
    # Django Admin Site
    path('admin/', admin.site.urls),

    # Health Check Endpoint
    path('api/health/', HealthCheckView.as_view(), name='health-check'),

    # Authentication & User Management
    path('api/', include('accounts.urls')),

    # Domain Applications
    path('api/machines/', include('machines.urls')),
    path('api/documents/', include('documents.urls')),
    path('api/rag/', include('rag.urls')),
    path('api/history/', include('history.urls')),
    path('api/supervisor/', include('history.urls')),

    # Visual Quality Inspection & Product Registry Endpoints
    path('api/inspections/', include('inspections.urls')),
    path('api/products/', include('inspections.product_urls')),
    path('api/supervisor/inspections/', SupervisorInspectionListView.as_view(), name='supervisor-inspection-list'),
    path('api/supervisor/inspections/<int:pk>/review/', SupervisorReviewView.as_view(), name='supervisor-inspection-review-direct'),
]

# Serve uploaded media assets (PDF manuals, inspection images) during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
