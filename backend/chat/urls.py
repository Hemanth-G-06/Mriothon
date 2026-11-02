"""
URL routing for Engineer Chat Conversations and Messages.
"""

from django.urls import path
from chat.views import (
    ConversationDetailView,
    ConversationListCreateView,
    ConversationMessagesView,
)

app_name = 'chat'

urlpatterns = [
    path('conversations/', ConversationListCreateView.as_view(), name='conversation-list'),
    path('conversations/<uuid:conversation_id>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<uuid:conversation_id>/messages/', ConversationMessagesView.as_view(), name='conversation-messages'),
]

