"""
Serializers for RAG document indexing and status inspection.
"""

from rest_framework import serializers
from rag.models import DocumentIndex


class DocumentIndexStatusSerializer(serializers.ModelSerializer):
    """
    Public representation of a Document's RAG indexing state.
    Excludes internal filesystem paths or embedding API credentials.
    """
    document_id = serializers.UUIDField(source='document.id', read_only=True)
    document_title = serializers.CharField(source='document.title', read_only=True)
    machine_id = serializers.UUIDField(source='document.machine.id', read_only=True)
    machine_code = serializers.CharField(source='document.machine.machine_code', read_only=True)

    class Meta:
        model = DocumentIndex
        fields = [
            'document_id',
            'document_title',
            'machine_id',
            'machine_code',
            'status',
            'chunk_count',
            'embedding_model',
            'error_message',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

