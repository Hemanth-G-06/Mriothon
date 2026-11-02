"""
Serializers for the History and AgentOps application.
Supports query records, relational citations, provenance ledgers, and supervisor escalations.
"""

from rest_framework import serializers
from history.models import (
    AuditEvent,
    AuditProvenanceRecord,
    Citation,
    Escalation,
    QueryRecord,
)


class QueryRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for query history records supporting both engineer self-inspection
    and supervisor audit monitoring.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    machine_name = serializers.CharField(source='machine.name', read_only=True)
    machine_code = serializers.CharField(source='machine.machine_code', read_only=True)
    machine_id = serializers.UUIDField(source='machine.id', read_only=True)
    engineer_name = serializers.CharField(read_only=True)
    is_insufficient_evidence = serializers.BooleanField(source='abstained', read_only=True)

    class Meta:
        model = QueryRecord
        fields = [
            'id',
            'user',
            'user_email',
            'user_full_name',
            'engineer_name',
            'machine',
            'machine_id',
            'machine_name',
            'machine_code',
            'question',
            'answer',
            'abstained',
            'is_insufficient_evidence',
            'citations',
            'evidence_status',
            'intent',
            'fault_code',
            'trace_id',
            'duration_ms',
            'created_at',
        ]
        read_only_fields = fields

    def get_user_full_name(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return "Plant Engineer"


# Alias QuestionRecordSerializer to QueryRecordSerializer for compatibility
QuestionRecordSerializer = QueryRecordSerializer


class CitationSerializer(serializers.ModelSerializer):
    """
    Relational citation serializer for verified claims.
    """
    class Meta:
        model = Citation
        fields = [
            'id',
            'query',
            'document',
            'document_title',
            'revision',
            'page_number',
            'chunk_id',
            'source_text',
            'similarity_score',
            'retrieval_method',
            'is_verified',
            'verification_notes',
            'created_at',
        ]
        read_only_fields = fields


class AuditProvenanceRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for tamper-resistant provenance audit ledger.
    """
    machine_code = serializers.CharField(source='machine.machine_code', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AuditProvenanceRecord
        fields = [
            'id',
            'request_id',
            'trace_id',
            'user',
            'user_email',
            'user_role',
            'machine',
            'machine_code',
            'query_record',
            'user_question',
            'query_classification',
            'agent_transitions',
            'retrieval_operations',
            'retrieved_document_ids',
            'evidence_chunks',
            'evidence_evaluation_outcome',
            'citation_validation_outcome',
            'final_answer',
            'latencies',
            'retry_attempts',
            'escalation_status',
            'model_name',
            'created_at',
        ]
        read_only_fields = fields


class EscalationSerializer(serializers.ModelSerializer):
    """
    Serializer for supervisor escalations.
    """
    machine_code = serializers.CharField(source='machine.machine_code', read_only=True)
    engineer_email = serializers.EmailField(source='engineer.email', read_only=True)

    class Meta:
        model = Escalation
        fields = [
            'id',
            'query',
            'machine',
            'machine_code',
            'engineer',
            'engineer_email',
            'reason',
            'status',
            'resolution_notes',
            'resolved_by',
            'resolved_at',
            'created_at',
        ]
        read_only_fields = ['id', 'query', 'machine', 'machine_code', 'engineer', 'engineer_email', 'created_at']


class AuditEventSerializer(serializers.ModelSerializer):
    """
    Serializer for administrative and security audit events.
    """
    machine_code = serializers.CharField(source='machine.machine_code', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            'id',
            'event_type',
            'user',
            'user_email',
            'user_role',
            'machine',
            'machine_code',
            'details',
            'ip_address',
            'timestamp',
        ]
        read_only_fields = fields


class AskQuestionRequestSerializer(serializers.Serializer):
    """
    Alternative input serializer for assistant question endpoints.
    """
    machine_id = serializers.UUIDField(required=True)
    question = serializers.CharField(required=True, min_length=3, max_length=1000)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    error_code = serializers.CharField(required=False, allow_blank=True, default='')
    symptoms = serializers.CharField(required=False, allow_blank=True, default='')
