"""
Serializers for Document Management and Extracted Page Text.
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
from documents.models import Document, DocumentPage
from documents.services import validate_pdf_upload
from machines.models import Machine


class DocumentListSerializer(serializers.ModelSerializer):
    """
    Compact serializer for listing documents.
    """
    machine_id = serializers.UUIDField(source='machine.id', read_only=True)
    machine_code = serializers.CharField(source='machine.machine_code', read_only=True)
    machine_name = serializers.CharField(source='machine.name', read_only=True)

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
            'machine_id',
            'machine_code',
            'machine_name',
            'title',
            'description',
            'original_filename',
            'file_size',
            'page_count',
            'status',
            'created_at',
            'updated_at',
            'is_active',
        ]
        read_only_fields = fields


class DocumentDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for inspecting document metadata.
    Excludes sensitive server filesystem paths.
    """
    machine_id = serializers.UUIDField(source='machine.id', read_only=True)
    machine_code = serializers.CharField(source='machine.machine_code', read_only=True)
    machine_name = serializers.CharField(source='machine.name', read_only=True)
    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'machine_id',
            'machine_code',
            'machine_name',
            'title',
            'description',
            'original_filename',
            'file_size',
            'checksum',
            'page_count',
            'status',
            'uploaded_by_email',
            'created_at',
            'updated_at',
            'is_active',
        ]
        read_only_fields = fields


class DocumentUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for uploading a new technical manual PDF (Administrator only).
    Enforces PDF signature verification, file size limit, and active machine checks.
    """
    machine_id = serializers.UUIDField(write_only=True)
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'machine_id',
            'title',
            'description',
            'file',
            'original_filename',
            'file_size',
            'checksum',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'original_filename', 'file_size', 'checksum', 'status', 'created_at']

    def validate(self, attrs):
        machine_id = attrs.get('machine_id')
        uploaded_file = attrs.get('file')

        try:
            machine = Machine.objects.get(pk=machine_id)
        except Machine.DoesNotExist:
            raise serializers.ValidationError({"machine_id": "Machine not found."})

        # Validate PDF through domain service
        checksum, file_size = validate_pdf_upload(uploaded_file, machine)

        attrs['machine'] = machine
        attrs['checksum'] = checksum
        attrs['file_size'] = file_size
        attrs['original_filename'] = uploaded_file.name
        return attrs

    def create(self, validated_data):
        validated_data.pop('machine_id', None)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['uploaded_by'] = request.user

        document = Document.objects.create(**validated_data)
        return document


class DocumentPageSerializer(serializers.ModelSerializer):
    """
    Serializer for retrieved extracted PDF page text.
    """

    class Meta:
        model = DocumentPage
        fields = [
            'id',
            'page_number',
            'character_count',
            'text',
            'created_at',
        ]
        read_only_fields = fields
