"""
URL routing for the Machines application.
"""

from rest_framework.routers import DefaultRouter
from machines.views import MachineViewSet

app_name = 'machines'

router = DefaultRouter()
router.register(r'', MachineViewSet, basename='machine')

urlpatterns = router.urls
