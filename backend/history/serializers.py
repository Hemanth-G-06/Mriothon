"""
Serializers for the History application.
"""

from rest_framework import serializers
from history.models import QueryRecord


class QueryRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for QA audit records and supervisor history inspection.
    """
    machine_id = serializers.IntegerField(source='machine.id', read_only=True)
    machine_name = serializers.CharField(source='machine.name', read_only=True)

    class Meta:
        model = QueryRecord
        fields = [
            'id',
            'machine',
            'machine_id',
            'machine_name',
            'user',
            'engineer_name',
            'question',
            'answer',
            'is_insufficient_evidence',
            'citations',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'machine_id', 'machine_name']
