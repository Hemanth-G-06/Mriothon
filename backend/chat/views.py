"""
Views for Engineer Chatbot Conversations and Messages.
Enforces strict ENGINEER role authorization, machine assignment validation,
and seamless integration with the evidence-gated RAG pipeline.
"""

import logging
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.models import Conversation, ChatMessage
from chat.permissions import IsEngineerUser
from chat.serializers import (
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
    ConversationCreateSerializer,
    ConversationDetailSerializer,
    ConversationListSerializer,
    ConversationUpdateSerializer,
)
from chat.services import execute_chat_rag_query
from machines.models import MachineStatus
from machines.services import can_user_access_machine
from rag.services.llm.base import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMModelUnavailableError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from rag.services.providers.base import EmbeddingProviderError
from rag.services.retrieval_service import RetrievalError

logger = logging.getLogger(__name__)


class ConversationListCreateView(APIView):
    """
    GET  /api/chat/conversations/ - List conversations belonging to the authenticated engineer.
    POST /api/chat/conversations/ - Create a new conversation for an authorized machine.
    """
    permission_classes = [IsEngineerUser]

    def get(self, request):
        qs = Conversation.objects.filter(user=request.user).select_related('machine').prefetch_related('messages')

        machine_id = request.query_params.get('machine_id')
        if machine_id:
            qs = qs.filter(machine_id=machine_id)

        serializer = ConversationListSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ConversationCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        machine = serializer.context['machine']
        title = serializer.validated_data.get('title') or 'New Conversation'

        conversation = Conversation.objects.create(
            user=request.user,
            machine=machine,
            title=title,
        )

        return Response(
            ConversationDetailSerializer(conversation).data,
            status=status.HTTP_201_CREATED,
        )


class ConversationDetailView(APIView):
    """
    GET    /api/chat/conversations/{id}/ - Retrieve conversation and its chronological messages.
    PATCH  /api/chat/conversations/{id}/ - Update conversation title.
    DELETE /api/chat/conversations/{id}/ - Permanently delete conversation and its messages.
    """
    permission_classes = [IsEngineerUser]

    def get_conversation(self, conversation_id, user):
        return Conversation.objects.filter(id=conversation_id).select_related('machine').prefetch_related('messages').first()

    def get(self, request, conversation_id):
        conversation = self.get_conversation(conversation_id, request.user)
        if not conversation:
            return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        if conversation.user != request.user:
            return Response({"detail": "Access denied. You do not own this conversation."}, status=status.HTTP_403_FORBIDDEN)

        # Enforce dynamic machine authorization check: if engineer was unassigned, deny access
        if not can_user_access_machine(request.user, conversation.machine):
            return Response(
                {"detail": f"Access denied. You are no longer assigned to machine '{conversation.machine.machine_code}'."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if conversation.machine.status != MachineStatus.ACTIVE:
            return Response(
                {"detail": f"Machine '{conversation.machine.machine_code}' is currently inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ConversationDetailSerializer(conversation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, conversation_id):
        conversation = self.get_conversation(conversation_id, request.user)
        if not conversation:
            return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        if conversation.user != request.user:
            return Response({"detail": "Access denied. You do not own this conversation."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ConversationUpdateSerializer(conversation, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(ConversationDetailSerializer(conversation).data, status=status.HTTP_200_OK)

    def delete(self, request, conversation_id):
        conversation = self.get_conversation(conversation_id, request.user)
        if not conversation:
            return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        if conversation.user != request.user:
            return Response({"detail": "Access denied. You do not own this conversation."}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            conversation.messages.all().delete()
            conversation.delete()

        return Response(
            {"detail": "Conversation successfully deleted.", "id": str(conversation_id)},
            status=status.HTTP_200_OK,
        )


class ConversationMessagesView(APIView):
    """
    POST /api/chat/conversations/{id}/messages/
    Submits a user message to the conversation, invokes the RAG pipeline using
    the conversation's machine context, persists the grounded answer and citations,
    and returns the updated response.
    """
    permission_classes = [IsEngineerUser]

    def post(self, request, conversation_id):
        conversation = Conversation.objects.filter(id=conversation_id).select_related('machine').first()
        if not conversation:
            return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        if conversation.user != request.user:
            return Response({"detail": "Access denied. You do not own this conversation."}, status=status.HTTP_403_FORBIDDEN)

        if not can_user_access_machine(request.user, conversation.machine):
            return Response(
                {"detail": f"Access denied. You are no longer assigned to machine '{conversation.machine.machine_code}'."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if conversation.machine.status != MachineStatus.ACTIVE:
            return Response(
                {"detail": f"Machine '{conversation.machine.machine_code}' is currently inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ChatMessageCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        content = serializer.validated_data['content']

        # 1. Persist the user message first
        user_message = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.USER,
            content=content,
        )

        # 2. Update conversation title if still the default
        if conversation.title in ('New Conversation', '') or not conversation.title:
            clean_title = content[:60].strip()
            if len(content) > 60:
                clean_title += '...'
            conversation.title = clean_title
            conversation.save(update_fields=['title', 'updated_at'])
        else:
            conversation.save(update_fields=['updated_at'])

        # 3. Invoke RAG pipeline using conversation's machine context
        try:
            rag_res = execute_chat_rag_query(
                user=request.user,
                machine=conversation.machine,
                question=content,
                conversation_id=str(conversation.id),
                ip_address=request.META.get('REMOTE_ADDR'),
            )
        except (LLMRateLimitError, LLMQuotaExhaustedError) as e:
            return Response(
                {
                    "error": (
                        "RAG pipeline service error: The AI answer generation service (Google Gemini) "
                        "is temporarily rate-limited or has reached its request quota. "
                        "Please wait 30-60 seconds and try again."
                    ),
                    "error_type": "llm_rate_limit",
                    "user_message": ChatMessageSerializer(user_message).data,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (LLMTimeoutError, LLMModelUnavailableError, LLMAuthenticationError, LLMConfigurationError, LLMProviderError) as e:
            return Response(
                {
                    "error": (
                        "RAG pipeline service error: The AI answer generation service (Google Gemini) "
                        "is temporarily unavailable. Please try again shortly."
                    ),
                    "error_type": "llm_unavailable",
                    "user_message": ChatMessageSerializer(user_message).data,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except EmbeddingProviderError as e:
            return Response(
                {
                    "error": (
                        "RAG pipeline service error: The embedding generation service is temporarily "
                        "unavailable or timed out. Please verify the local embedding server is running."
                    ),
                    "error_type": "embedding_unavailable",
                    "user_message": ChatMessageSerializer(user_message).data,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except RetrievalError as e:
            return Response(
                {
                    "error": (
                        "RAG pipeline service error: Database vector retrieval failed while searching "
                        "machine documentation. Please try again later."
                    ),
                    "error_type": "retrieval_error",
                    "user_message": ChatMessageSerializer(user_message).data,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error during chat message RAG processing: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred while processing the manual query.",
                    "user_message": ChatMessageSerializer(user_message).data,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 4. Persist the assistant message
        assistant_message = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.ASSISTANT,
            content=rag_res['answer'],
            citations=rag_res['citations'],
            metadata={
                'abstained': rag_res['abstained'],
                'is_insufficient_evidence': rag_res['abstained'],
                'evidence_status': rag_res['evidence_status'],
                'trace_id': rag_res['trace_id'],
                'query_id': str(rag_res['query_record'].id),
            },
        )
        conversation.save(update_fields=['updated_at'])

        return Response(
            {
                "user_message": ChatMessageSerializer(user_message).data,
                "assistant_message": ChatMessageSerializer(assistant_message).data,
                "answer": rag_res['answer'],
                "citations": rag_res['citations'],
                "abstained": rag_res['abstained'],
                "is_insufficient_evidence": rag_res['abstained'],
            },
            status=status.HTTP_201_CREATED,
        )

