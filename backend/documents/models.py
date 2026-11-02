"""
Document and DocumentPage models for the Manufacturing Manual Assistant.
Handles technical manual PDF metadata, safe file storage, and extracted page text.
"""

import os
import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from machines.models import Machine


class DocumentStatus(models.TextChoices):
    """
    Lifecycle processing states for uploaded PDF manuals.
    """
    UPLOADED = 'UPLOADED', _('Uploaded')
    PROCESSING = 'PROCESSING', _('Processing')
    READY = 'READY', _('Ready')
    FAILED = 'FAILED', _('Failed')


def document_file_upload_path(instance, filename):
    """
    Generates a secure, non-guessable storage path for uploaded manual PDFs:
    e.g. documents/manuals/<machine_id>/<uuid>.pdf
    Prevents path traversal and separates stored filesystem names from original user filenames.
    """
    ext = os.path.splitext(filename)[1].lower() or '.pdf'
    return f'documents/manuals/{instance.machine_id}/{uuid.uuid4()}{ext}'


class Document(models.Model):
    """
    Represents an uploaded technical manual associated with a specific machine.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_('Unique document UUID identifier.')
    )
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_('machine')
    )
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    file = models.FileField(
        _('PDF file'),
        upload_to=document_file_upload_path,
        help_text=_('Uploaded original manual PDF.')
    )
    original_filename = models.CharField(
        _('original filename'),
        max_length=255,
        help_text=_('Preserved client filename.')
    )
    file_size = models.PositiveBigIntegerField(
        _('file size (bytes)'),
        default=0,
        help_text=_('Size of the original file in bytes.')
    )
    checksum = models.CharField(
        _('SHA-256 checksum'),
        max_length=64,
        db_index=True,
        help_text=_('Cryptographic SHA-256 checksum for duplicate detection.')
    )
    page_count = models.PositiveIntegerField(
        _('page count'),
        default=0,
        help_text=_('Total page count determined after PDF parsing.')
    )
    status = models.CharField(
        _('processing status'),
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.UPLOADED,
        db_index=True,
        help_text=_('Processing state of text extraction.')
    )
    processing_error = models.TextField(
        _('processing error'),
        blank=True,
        help_text=_('Internal error description if extraction failed (sanitized from public API).')
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents',
        verbose_name=_('uploaded by')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        db_index=True,
        help_text=_('Soft-deactivation flag for document management.')
    )

    class Meta:
        db_table = 'documents'
        verbose_name = _('document')
        verbose_name_plural = _('documents')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['machine', 'checksum'],
                condition=models.Q(is_active=True),
                name='unique_active_machine_document_checksum'
            )
        ]

    def __str__(self):
        return f"{self.title} ({self.machine.machine_code}) [{self.status}]"


class DocumentPage(models.Model):
    """
    Stores extracted text from an individual page of a PDF manual.
    Preserves original page numbering for precise citation and RAG retrieval.
    """
    id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='pages',
        verbose_name=_('document')
    )
    page_number = models.PositiveIntegerField(
        _('page number'),
        help_text=_('1-indexed original PDF page number.')
    )
    text = models.TextField(
        _('extracted text'),
        blank=True,
        help_text=_('Raw extracted machine-readable text for this page.')
    )
    character_count = models.PositiveIntegerField(
        _('character count'),
        default=0,
        help_text=_('Total character count of extracted text on this page.')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        db_table = 'document_pages'
        verbose_name = _('document page')
        verbose_name_plural = _('document pages')
        ordering = ['document', 'page_number']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'page_number'],
                name='unique_document_page_number'
            )
        ]

    def __str__(self):
        return f"Document {self.document_id} - Page {self.page_number} ({self.character_count} chars)"
