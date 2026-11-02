"""
Django admin configuration for RAG models.
"""

from django.contrib import admin
from rag.models import DocumentChunk, DocumentIndex


@admin.register(DocumentIndex)
class DocumentIndexAdmin(admin.ModelAdmin):
    list_display = ('document', 'status', 'chunk_count', 'embedding_model', 'updated_at')
    list_filter = ('status', 'embedding_model')
    search_fields = ('document__title', 'document__id', 'embedding_model')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'page', 'chunk_index', 'token_count', 'chroma_vector_id', 'created_at')
    list_filter = ('embedding_model',)
    search_fields = ('document__title', 'chroma_vector_id', 'text')
    readonly_fields = ('id', 'created_at')

