"""
Views and API endpoints for Document Management, Page Text Extraction, and Secure Downloads.
"""

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin
from documents.models import Document, DocumentStatus
from documents.permissions import CanAccessDocumentObject, IsAdminUserOrReadOnly
from documents.serializers import (
    DocumentDetailSerializer,
    DocumentListSerializer,
    DocumentPageSerializer,
    DocumentUploadSerializer,
)
from documents.services import (
    can_user_access_document,
    extract_document_pages,
    get_accessible_documents_queryset,
)
from machines.models import Machine
from machines.services import can_user_access_machine


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for technical manual documents:
    - GET /api/documents/ (List accessible documents; optional ?machine_id= filter)
    - POST /api/documents/ (Administrator only: upload PDF)
    - GET /api/documents/{id}/ (Retrieve metadata if authorized)
    - DELETE /api/documents/{id}/ (Administrator only: soft-deactivate)
    """
    permission_classes = [IsAuthenticated, IsAdminUserOrReadOnly, CanAccessDocumentObject]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        machine_id = self.request.query_params.get('machine_id')
        return get_accessible_documents_queryset(self.request.user, machine_id=machine_id)

    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentUploadSerializer
        elif self.action == 'retrieve':
            return DocumentDetailSerializer
        return DocumentListSerializer

    def create(self, request, *args, **kwargs):
        """
        Uploads a PDF manual, saves the document record, and triggers synchronous page extraction.
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        # Perform page extraction
        extract_document_pages(document)

        # Refresh from database to reflect extraction outcome (READY or FAILED)
        document.refresh_from_db()
        detail_serializer = DocumentDetailSerializer(document)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """
        Soft-deactivate a document rather than physically deleting records or files.
        """
        document = self.get_object()
        document.is_active = False
        document.save(update_fields=['is_active', 'updated_at'])

        return Response(
            {
                "detail": "Document successfully deactivated.",
                "id": str(document.id),
                "is_active": document.is_active,
            },
            status=status.HTTP_200_OK
        )


class DocumentPagesView(APIView):
    """
    Endpoint for retrieving extracted page text:
    - GET /api/documents/{id}/pages/ (Supports ?page_number= filter)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(Document, pk=document_id)

        if not can_user_access_document(request.user, document):
            raise PermissionDenied("You do not have permission to view pages for this document.")

        pages_qs = document.pages.all().order_by('page_number')

        # Optional page_number filter
        page_number = request.query_params.get('page_number')
        if page_number:
            try:
                page_num_int = int(page_number)
                pages_qs = pages_qs.filter(page_number=page_num_int)
            except ValueError:
                pass

        serializer = DocumentPageSerializer(pages_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DocumentDownloadView(APIView):
    """
    Endpoint for secure, authenticated original PDF downloads:
    - GET /api/documents/{id}/download/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(Document, pk=document_id)

        if not can_user_access_document(request.user, document):
            raise PermissionDenied("You do not have permission to download this document.")

        if not document.file:
            raise Http404("Document file not found.")

        try:
            file_handle = document.file.open('rb')
        except FileNotFoundError:
            raise Http404("The requested file does not exist on disk.")

        response = FileResponse(
            file_handle,
            content_type='application/pdf',
            as_attachment=True,
            filename=document.original_filename
        )
        return response


class MachineDocumentsListView(APIView):
    """
    Endpoint for machine-specific document listings:
    - GET /api/machines/{machine_id}/documents/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, machine_id):
        machine = get_object_or_404(Machine, pk=machine_id)

        if not can_user_access_machine(request.user, machine):
            raise PermissionDenied("You do not have permission to view documents for this machine.")

        documents_qs = get_accessible_documents_queryset(request.user, machine_id=machine_id)
        serializer = DocumentListSerializer(documents_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
