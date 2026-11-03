"""
URL configuration for the Manufacturing Manual Assistant project.

Root API URL routing mapping to domain applications, system endpoints,
Prometheus metrics, and versioned APIs.
"""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from django.conf import settings
from django.conf.urls.static import static
from config.views import HealthCheckView


def metrics_view(request):
    """Prometheus metrics scrape endpoint."""
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)


v1_patterns = [
    path('health/', HealthCheckView.as_view(), name='v1-health-check'),
    path('auth/', include('accounts.urls')),
    path('machines/', include('machines.urls')),
    path('documents/', include('documents.urls')),
    path('rag/', include('rag.urls')),
    path('history/', include('history.urls')),
]

urlpatterns = [
    # Django Admin Site
    path('admin/', admin.site.urls),

    # Prometheus Metrics Scrape Endpoint
    path('metrics', metrics_view, name='prometheus-metrics'),
    path('metrics/', metrics_view, name='prometheus-metrics-slash'),

    # Health Check Endpoint
    path('api/health/', HealthCheckView.as_view(), name='health-check'),

    # Versioned v1 API Compatibility
    path('api/v1/', include((v1_patterns, 'v1'))),

    # Authentication & User Management
    path('api/', include('accounts.urls')),

    # Quality Inspection & Products Catalog (Round 2)
    path('api/products/', include('inspections.product_urls')),
    path('api/inspections/', include('inspections.urls')),
    path('api/supervisor/inspections/', include('inspections.supervisor_urls')),

    # Domain Applications
    path('api/machines/', include('machines.urls')),
    path('api/documents/', include('documents.urls')),
    path('api/rag/', include('rag.urls')),
    path('api/chat/', include(('chat.urls', 'chat'), namespace='chat')),
    path('api/chat/ask/', include(('rag.urls', 'chat_ask'), namespace='chat_ask')),
    path('api/chat/history/', include(('history.urls', 'chat_history'), namespace='chat_history')),
    path('api/history/', include('history.urls')),
    path('api/supervisor/', include(('history.urls', 'supervisor'), namespace='supervisor')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

