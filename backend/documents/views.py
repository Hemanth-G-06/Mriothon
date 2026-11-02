import logging
from django.db import transaction
from rag.services.chroma_service import ChromaService
logger = logging.getLogger(__name__)
"""
Views and API endpoints for Document Management, Page Text Extraction, and Secure Downloads.
"""

import os
import re
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserRole
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
        Deletes or deactivates a document.
        - Admin only.
        - If ?permanent=true (or default delete action):
          Removes associated ChromaDB vectors, deletes the physical PDF file,
          and removes relational DocumentPage, DocumentChunk, DocumentIndex, and Document records.
        - If ?permanent=false:
          Soft-deactivates the document (sets is_active to False).
        """
        if request.user.role != UserRole.ADMIN and not request.user.is_superuser:
            raise PermissionDenied("Only Administrators can delete or deactivate technical manuals.")

        document = self.get_object()
        permanent = request.query_params.get('permanent', 'false').lower() in ['true', '1']

        if not permanent:
            document.is_active = False
            document.save(update_fields=['is_active', 'updated_at'])
            return Response(
                {
                    "detail": "Document successfully deactivated.",
                    "id": str(document.id),
                    "is_active": document.is_active,
                    "deleted": False,
                },
                status=status.HTTP_200_OK
            )

        # Permanent deletion workflow
        doc_id_str = str(document.id)
        doc_title = document.title

        # 1. Clean up ChromaDB vectors only when legacy chroma backend is active
        from django.conf import settings as _settings
        if getattr(_settings, 'VECTOR_BACKEND', 'pgvector') == 'chroma':
            try:
                chroma_service = ChromaService()
                chroma_service.delete_document_vectors(doc_id_str)
            except Exception as exc:
                logger.warning("Error deleting ChromaDB vectors for document %s: %s", doc_id_str, exc)

        # 2. Clean up physical PDF file from storage
        try:
            if document.file:
                document.file.delete(save=False)
        except Exception as exc:
            logger.warning("Error deleting PDF file for document %s: %s", doc_id_str, exc)

        # 3. Atomic relational cascade deletion (removes DocumentPage, DocumentChunk, DocumentIndex)
        with transaction.atomic():
            document.delete()

        return Response(
            {
                "detail": f"Document '{doc_title}' and its vector index successfully deleted.",
                "id": doc_id_str,
                "title": doc_title,
                "deleted": True,
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




class DocumentViewerView(APIView):
    """
    Endpoint for secure, authenticated original PDF streaming and inline viewing:
    - GET /api/documents/{id}/pdf/
    - GET /api/documents/{id}/view/

    Enforces authentication and machine-level authorization.
    Supports HTTP 206 Partial Content byte-range requests and standard inline PDF delivery.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(Document, pk=document_id)

        # Enforce RBAC and machine-level authorization
        if not can_user_access_document(request.user, document):
            raise PermissionDenied("You do not have permission to view this technical manual.")

        if not document.file:
            raise Http404("Document file record is empty.")

        # Verify physical file existence safely without path leakage
        try:
            file_path = document.file.path
            if not os.path.exists(file_path):
                raise Http404("The requested technical manual PDF file does not exist on disk.")
        except (AttributeError, NotImplementedError):
            if not document.file.storage.exists(document.file.name):
                raise Http404("The requested technical manual PDF file does not exist on storage.")
            file_path = None

        # Determine total file size
        try:
            if file_path:
                file_size = os.path.getsize(file_path)
            else:
                file_size = document.file.size
        except Exception:
            file_size = document.file_size or 0

        original_filename = document.original_filename or "manual.pdf"
        safe_filename = original_filename.replace('"', '\"')

        # Check for HTTP Range header
        range_header = request.META.get('HTTP_RANGE', '').strip()

        if range_header:
            range_match = re.match(r'^bytes=\s*(\d*)\s*-\s*(\d*)$', range_header)
            if not range_match:
                response = HttpResponse(status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
                response['Content-Range'] = f'bytes */{file_size}'
                response['Accept-Ranges'] = 'bytes'
                return response

            start_str, end_str = range_match.groups()

            if start_str and end_str:
                start = int(start_str)
                end = int(end_str)
                if start > end or start >= file_size:
                    response = HttpResponse(status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
                    response['Content-Range'] = f'bytes */{file_size}'
                    response['Accept-Ranges'] = 'bytes'
                    return response
                end = min(end, file_size - 1)
            elif start_str:
                start = int(start_str)
                if start >= file_size:
                    response = HttpResponse(status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
                    response['Content-Range'] = f'bytes */{file_size}'
                    response['Accept-Ranges'] = 'bytes'
                    return response
                end = file_size - 1
            elif end_str:
                suffix = int(end_str)
                if suffix <= 0:
                    response = HttpResponse(status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
                    response['Content-Range'] = f'bytes */{file_size}'
                    response['Accept-Ranges'] = 'bytes'
                    return response
                start = max(0, file_size - suffix)
                end = file_size - 1
            else:
                response = HttpResponse(status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
                response['Content-Range'] = f'bytes */{file_size}'
                response['Accept-Ranges'] = 'bytes'
                return response

            content_length = (end - start) + 1

            # Memory-efficient chunked range streamer
            def range_generator(f_obj, offset, length, chunk_size=65536):
                try:
                    f_obj.seek(offset)
                    bytes_remaining = length
                    while bytes_remaining > 0:
                        chunk = f_obj.read(min(chunk_size, bytes_remaining))
                        if not chunk:
                            break
                        bytes_remaining -= len(chunk)
                        yield chunk
                finally:
                    f_obj.close()

            file_obj = open(file_path, 'rb') if file_path else document.file.open('rb')
            response = StreamingHttpResponse(
                range_generator(file_obj, start, content_length),
                status=status.HTTP_206_PARTIAL_CONTENT,
                content_type='application/pdf'
            )
            response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response['Content-Length'] = str(content_length)
            response['Content-Disposition'] = f'inline; filename="{safe_filename}"'
            response['Accept-Ranges'] = 'bytes'
            response['Cache-Control'] = 'private, max-age=3600'
            response['X-Content-Type-Options'] = 'nosniff'
            return response

        # Standard GET response (no range requested)
        file_obj = open(file_path, 'rb') if file_path else document.file.open('rb')
        response = FileResponse(
            file_obj,
            content_type='application/pdf',
            as_attachment=False,
            filename=original_filename
        )
        response['Content-Disposition'] = f'inline; filename="{safe_filename}"'
        response['Accept-Ranges'] = 'bytes'
        response['Content-Length'] = str(file_size)
        response['Cache-Control'] = 'private, max-age=3600'
        response['X-Content-Type-Options'] = 'nosniff'
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
