"""
Serializers for RAG document indexing and AgentOps question answering inspection.
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


class RagQueryRequestSerializer(serializers.Serializer):
    """
    Validates input parameters for a RAG question answering query.
    """
    machine_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the machine whose manuals should be queried."
    )
    question = serializers.CharField(
        required=True,
        min_length=3,
        max_length=1000,
        trim_whitespace=True,
        help_text="Technical question regarding the machine manual."
    )
    conversation_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional conversation or session UUID."
    )
    fault_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        help_text="Optional machine error/fault code."
    )


class RagCitationSerializer(serializers.Serializer):
    """
    Verified citation information pointing to a real document and page in Neon PostgreSQL.
    """
    document_id = serializers.UUIDField()
    document_title = serializers.CharField()
    page_number = serializers.IntegerField()
    source_id = serializers.CharField(required=False, allow_blank=True)
    revision = serializers.CharField(required=False, default='1.0')
    source_text = serializers.CharField(required=False, allow_blank=True)


class RagQueryResponseSerializer(serializers.Serializer):
    """
    Response schema for RAG and Agentic answer generation.
    Supports backwards compatibility with existing frontend and tests.
    """
    answer = serializers.CharField()
    citations = RagCitationSerializer(many=True)
    abstained = serializers.BooleanField()
    is_insufficient_evidence = serializers.BooleanField(required=False)
    query_id = serializers.UUIDField(required=False)
    trace_id = serializers.CharField(required=False)
    evidence_status = serializers.CharField(required=False)
    agent_transitions = serializers.ListField(required=False)
