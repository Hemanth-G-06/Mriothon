"""
URL routing for the RAG and Agentic Assistant application.
Provides endpoints for querying grounded manuals and checking indexing status.
"""

from django.urls import path
from rag.views import RagQueryView, AssistantAskView

app_name = 'rag'

urlpatterns = [
    # Primary endpoint for question answering
    path('query/', RagQueryView.as_view(), name='rag-query'),
    # Alias matching frontend chatService.js
    path('ask/', AssistantAskView.as_view(), name='rag-ask'),
]
