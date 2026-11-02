"""
URL routing for Products catalog endpoints (/api/products/).
"""

from django.urls import path
from inspections.views import ProductListCreateView, ProductDetailView

urlpatterns = [
    path('', ProductListCreateView.as_view(), name='product-list-create'),
    path('<str:pk>/', ProductDetailView.as_view(), name='product-detail'),
]
