"""
Views and API endpoints for the Documents application.
"""

import io
from django.http import FileResponse, HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import IsAdminOrReadOnly
from documents.models import Document
from documents.serializers import DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for technical document assets:
    - GET /api/documents/ (List documents, filterable by ?machine_id=)
    - POST /api/documents/ or POST /api/documents/upload/ (Upload manual)
    - GET /api/documents/{id}/ (Retrieve document details)
    - GET /api/documents/{id}/pdf/ (View/Stream PDF)
    - GET /api/documents/{id}/download/ (Download PDF)
    """
    queryset = Document.objects.select_related('machine').all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        machine_id = self.request.query_params.get('machine_id') or self.request.query_params.get('machine')
        if machine_id:
            queryset = queryset.filter(machine_id=machine_id)
        return queryset

    def perform_create(self, serializer):
        uploaded_file = self.request.FILES.get('file')
        file_name = uploaded_file.name if uploaded_file else serializer.validated_data.get('file_name', '')
        file_size = uploaded_file.size if uploaded_file else serializer.validated_data.get('file_size', 0)

        serializer.save(
            file_name=file_name,
            file_size=file_size,
            status='Indexed'  # In this deployment, mark as Indexed immediately for RAG accessibility
        )

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request, *args, **kwargs):
        """
        Explicit upload endpoint: POST /api/documents/upload/
        """
        return self.create(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='pdf')
    def stream_pdf(self, request, pk=None):
        """
        GET /api/documents/{id}/pdf/
        Streams the manual PDF for inline viewing.
        """
        document = self.get_object()
        if document.file and hasattr(document.file, 'path'):
            try:
                response = FileResponse(open(document.file.path, 'rb'), content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="{document.file_name or "manual.pdf"}"'
                return response
            except FileNotFoundError:
                pass

        # Return lightweight valid placeholder PDF bytes if physical file is pending
        placeholder_pdf = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
        )
        response = HttpResponse(placeholder_pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{document.file_name or "manual.pdf"}"'
        return response

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """
        GET /api/documents/{id}/download/
        Downloads the manual PDF as attachment.
        """
        response = self.stream_pdf(request, pk)
        document = self.get_object()
        response['Content-Disposition'] = f'attachment; filename="{document.file_name or "manual.pdf"}"'
        return response
