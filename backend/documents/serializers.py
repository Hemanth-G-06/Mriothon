"""
Serializers for the Documents application.
"""

from rest_framework import serializers
from documents.models import Document
from machines.models import Machine


class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for technical manuals and PDF documents.
    Supports upload, metadata inspection, and machine association.
    """
    machine_id = serializers.PrimaryKeyRelatedField(
        queryset=Machine.objects.all(),
        source='machine',
        write_only=False
    )
    machine_name = serializers.CharField(source='machine.name', read_only=True)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id',
            'machine',
            'machine_id',
            'machine_name',
            'title',
            'manual_type',
            'model_number',
            'revision',
            'file',
            'file_name',
            'file_size',
            'status',
            'pdf_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'machine_name', 'pdf_url']
        extra_kwargs = {
            'machine': {'write_only': True, 'required': False}
        }

    def get_pdf_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f"/api/documents/{obj.id}/pdf/")
        return f"/api/documents/{obj.id}/pdf/"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ensure machine_id is an integer in output
        data['machine_id'] = instance.machine.id
        return data
