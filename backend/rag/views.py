"""
API views for triggering document indexing and checking index status.
Enforces strict role-based access control and machine-level authorization.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from accounts.models import UserRole
from documents.models import Document, DocumentStatus
from documents.services import can_user_access_document
from rag.models import DocumentIndex, IndexingStatus
from rag.serializers import DocumentIndexStatusSerializer
from rag.services.indexing_service import (
    DocumentIndexingService,
    DocumentIndexingError,
    DocumentNotReadyForIndexingError,
)


class DocumentIndexTriggerView(APIView):
    """
    POST /api/documents/{document_id}/index/
    Restricted strictly to Administrators.
    Triggers chunking, embedding generation, and ChromaDB indexing for an eligible document.
    Rejects documents that have not completed PDF extraction.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        # Strict Administrator check
        if request.user.role != UserRole.ADMIN and not request.user.is_superuser:
            return Response(
                {"detail": "Only Administrators are authorized to trigger document indexing."},
                status=status.HTTP_403_FORBIDDEN
            )

        document = get_object_or_404(Document, id=document_id, is_active=True)

        if document.status != DocumentStatus.READY:
            return Response(
                {
                    "error": (
                        f"Document '{document.title}' cannot be indexed. "
                        f"Current PDF extraction status is '{document.status}'. "
                        f"Only documents with status 'READY' can be indexed."
                    ),
                    "document_status": document.status,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        indexing_service = DocumentIndexingService()
        try:
            index_record = indexing_service.index_document(document)
            serializer = DocumentIndexStatusSerializer(index_record)
            return Response(
                {
                    "message": f"Document '{document.title}' successfully indexed.",
                    "index": serializer.data,
                },
                status=status.HTTP_200_OK
            )
        except DocumentNotReadyForIndexingError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DocumentIndexingError as e:
            return Response(
                {
                    "error": f"Indexing operation failed: {e}",
                    "document_id": str(document.id),
                    "status": IndexingStatus.FAILED,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentIndexStatusView(APIView):
    """
    GET /api/documents/{document_id}/index-status/
    Accessible to Administrators, Supervisors, and actively assigned Engineers.
    Respects existing centralized machine-level access control.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(Document, id=document_id, is_active=True)

        # Machine-level authorization check
        if not can_user_access_document(request.user, document):
            return Response(
                {"detail": "You do not have permission to view documents or indexing status for this machine."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get or return default pending record
        index_record = DocumentIndex.objects.filter(document=document).first()
        if not index_record:
            # Document has not yet been queued for indexing
            return Response(
                {
                    "document_id": str(document.id),
                    "document_title": document.title,
                    "machine_id": str(document.machine.id),
                    "machine_code": document.machine.machine_code,
                    "status": IndexingStatus.PENDING,
                    "chunk_count": 0,
                    "embedding_model": "",
                    "error_message": "",
                    "created_at": None,
                    "updated_at": None,
                },
                status=status.HTTP_200_OK
            )

        serializer = DocumentIndexStatusSerializer(index_record)
        return Response(serializer.data, status=status.HTTP_200_OK)
