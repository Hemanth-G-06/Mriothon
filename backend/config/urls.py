"""
URL configuration for the Manufacturing Manual Assistant project.

Root API URL routing mapping to domain applications and system endpoints.
"""

from django.contrib import admin
from django.urls import include, path
from config.views import HealthCheckView

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
]
