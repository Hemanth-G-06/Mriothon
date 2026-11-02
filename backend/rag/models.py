"""
Relational models for RAG document chunking and indexing lifecycle.
Stores chunk metadata and indexing state in Neon PostgreSQL without vector embeddings.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from documents.models import Document, DocumentPage


class IndexingStatus(models.TextChoices):
    """
    Lifecycle states for document chunking and vector indexing.
    Separated from PDF extraction status to prevent lifecycle ambiguity.
    """
    PENDING = 'PENDING', _('Pending')
    PROCESSING = 'PROCESSING', _('Processing')
    READY = 'READY', _('Ready')
    FAILED = 'FAILED', _('Failed')


class DocumentIndex(models.Model):
    """
    Tracks indexing lifecycle, chunk count, embedding model, and errors
    for a specific Document in the RAG pipeline.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_('Unique document index UUID identifier.')
    )
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='index_record',
        verbose_name=_('document')
    )
    status = models.CharField(
        _('indexing status'),
        max_length=20,
        choices=IndexingStatus.choices,
        default=IndexingStatus.PENDING,
        db_index=True,
        help_text=_('Status of document vector indexing.')
    )
    chunk_count = models.PositiveIntegerField(
        _('chunk count'),
        default=0,
        help_text=_('Total number of chunks generated and indexed in ChromaDB.')
    )
    embedding_model = models.CharField(
        _('embedding model'),
        max_length=255,
        blank=True,
        help_text=_('Embedding model used to generate chunk vectors.')
    )
    error_message = models.TextField(
        _('error message'),
        blank=True,
        help_text=_('Internal error description if indexing failed.')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        db_table = 'document_indexes'
        verbose_name = _('document index')
        verbose_name_plural = _('document indexes')
        ordering = ['-updated_at']

    def __str__(self):
        return f"Index for Document {self.document_id} [{self.status}] ({self.chunk_count} chunks)"


class DocumentChunk(models.Model):
    """
    Stores chunk text and metadata in Neon PostgreSQL.
    Embedding vectors are strictly stored in ChromaDB, never in PostgreSQL.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_('Unique chunk UUID primary identifier.')
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name=_('document')
    )
    page = models.ForeignKey(
        DocumentPage,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name=_('document page')
    )
    chunk_index = models.PositiveIntegerField(
        _('chunk index'),
        help_text=_('0-indexed sequence position of the chunk on this specific page.')
    )
    text = models.TextField(
        _('chunk text'),
        help_text=_('Extracted text content of this chunk.')
    )
    token_count = models.PositiveIntegerField(
        _('token count'),
        default=0,
        help_text=_('Estimated token count of this chunk.')
    )
    character_start_offset = models.PositiveIntegerField(
        _('character start offset'),
        default=0,
        help_text=_('Starting character index within original page text.')
    )
    character_end_offset = models.PositiveIntegerField(
        _('character end offset'),
        default=0,
        help_text=_('Ending character index within original page text.')
    )
    chroma_vector_id = models.CharField(
        _('ChromaDB vector ID'),
        max_length=128,
        db_index=True,
        help_text=_('Deterministic vector identifier in ChromaDB collection.')
    )
    embedding_model = models.CharField(
        _('embedding model'),
        max_length=255,
        help_text=_('Identifier of embedding model used to vectorize this chunk.')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        db_table = 'document_chunks'
        verbose_name = _('document chunk')
        verbose_name_plural = _('document chunks')
        ordering = ['page', 'chunk_index']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'page', 'chunk_index'],
                name='unique_document_page_chunk_index'
            )
        ]
        indexes = [
            models.Index(fields=['document', 'page']),
            models.Index(fields=['chroma_vector_id']),
        ]

    def __str__(self):
        return f"Doc {self.document_id} Page {self.page.page_number} Chunk #{self.chunk_index} ({self.token_count} tokens)"

