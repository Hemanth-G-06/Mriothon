"""
Django Admin interface registration for Document and DocumentPage models.
"""

from django.contrib import admin
from documents.models import Document, DocumentPage


class DocumentPageInline(admin.TabularInline):
    model = DocumentPage
    extra = 0
    fields = ('page_number', 'character_count', 'created_at')
    readonly_fields = ('page_number', 'character_count', 'created_at')
    can_delete = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'machine',
        'status',
        'page_count',
        'file_size',
        'is_active',
        'uploaded_by',
        'created_at',
    )
    list_filter = ('status', 'is_active', 'machine', 'created_at')
    search_fields = ('title', 'original_filename', 'machine__machine_code', 'machine__name', 'checksum')
    ordering = ('-created_at',)
    inlines = [DocumentPageInline]
    readonly_fields = (
        'id',
        'checksum',
        'file_size',
        'page_count',
        'status',
        'processing_error',
        'uploaded_by',
        'created_at',
        'updated_at',
    )


@admin.register(DocumentPage)
class DocumentPageAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'page_number', 'character_count', 'created_at')
    list_filter = ('document__machine', 'created_at')
    search_fields = ('document__title', 'document__machine__machine_code', 'text')
    ordering = ('document', 'page_number')
    readonly_fields = ('document', 'page_number', 'character_count', 'text', 'created_at')
