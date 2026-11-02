"""
Document services for PDF validation, PyMuPDF text extraction, and access authorization.
"""

import hashlib
import os
import pymupdf
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import UserRole
from documents.models import Document, DocumentPage, DocumentStatus
from machines.models import Machine
from machines.services import can_user_access_machine, get_accessible_machines_queryset


def validate_pdf_upload(uploaded_file, machine: Machine):
    """
    Validates uploaded file against security, type, and business constraints:
    1. File is provided and non-empty.
    2. File extension is .pdf.
    3. Content contains valid PDF magic signature.
    4. Size is within MAX_UPLOAD_SIZE_BYTES.
    5. PyMuPDF can successfully open and parse the document.
    6. Machine is active.
    7. No active duplicate with identical checksum exists for this machine.

    Returns:
        tuple (checksum_hex: str, file_size_bytes: int)
    """
    if not uploaded_file:
        raise ValidationError({"file": "No file was provided."})

    # Validate filename and extension
    original_name = uploaded_file.name or ""
    ext = os.path.splitext(original_name)[1].lower()
    if ext != '.pdf':
        raise ValidationError({"file": f"Unsupported file extension '{ext}'. Only .pdf files are accepted."})

    # Check file size
    max_size = getattr(settings, 'MAX_UPLOAD_SIZE_BYTES', 25 * 1024 * 1024)
    file_size = uploaded_file.size

    if file_size <= 0:
        raise ValidationError({"file": "Uploaded file is empty (0 bytes)."})

    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValidationError({"file": f"File size exceeds the maximum allowed limit of {max_mb:.0f} MB."})

    # Read bytes for checksum and magic header validation
    file_content = uploaded_file.read()
    uploaded_file.seek(0)  # Reset pointer for storage backend

    # Verify PDF signature (%PDF-)
    if not file_content.startswith(b'%PDF-'):
        raise ValidationError({"file": "Invalid file content. The file does not have a valid PDF header signature."})

    # Compute SHA-256 checksum
    checksum = hashlib.sha256(file_content).hexdigest()

    # Validate target machine status
    if not machine.is_active:
        raise ValidationError({"machine": f"Cannot upload documents to inactive machine '{machine.machine_code}'."})

    # Check for active duplicate on this machine
    if Document.objects.filter(machine=machine, checksum=checksum, is_active=True).exists():
        raise ValidationError({
            "file": f"An identical active document already exists for machine '{machine.machine_code}'."
        })

    # Validate PyMuPDF can open the PDF stream
    try:
        doc = pymupdf.open(stream=file_content, filetype="pdf")
        if doc.page_count < 1:
            raise ValidationError({"file": "The PDF document contains no pages."})
        doc.close()
    except Exception as exc:
        raise ValidationError({"file": f"Unable to parse PDF document: {str(exc)}"})

    return checksum, file_size


def extract_document_pages(document: Document) -> bool:
    """
    Extracts text page by page from the document's PDF file using PyMuPDF.
    Ensures transactional consistency:
    - Creates DocumentPage records for each page (preserving 1-indexed page numbering).
    - Detects and rejects scanned/image-only PDFs (no extractable text).
    - Sets document status to READY on success or FAILED on error.

    Returns:
        bool: True if extraction succeeded, False if failed.
    """
    document.status = DocumentStatus.PROCESSING
    document.save(update_fields=['status', 'updated_at'])

    try:
        # Open file from storage
        document.file.open('rb')
        pdf_bytes = document.file.read()
        document.file.close()

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        total_pages = doc.page_count

        if total_pages < 1:
            document.status = DocumentStatus.FAILED
            document.processing_error = "PDF contains zero pages."
            document.save(update_fields=['status', 'processing_error', 'updated_at'])
            doc.close()
            return False

        pages_to_create = []
        total_characters = 0

        for page_index in range(total_pages):
            page_num = page_index + 1
            page = doc.load_page(page_index)
            raw_text = page.get_text("text") or ""
            stripped_text = raw_text.strip()
            char_count = len(stripped_text)
            total_characters += char_count

            pages_to_create.append(
                DocumentPage(
                    document=document,
                    page_number=page_num,
                    text=raw_text,
                    character_count=len(raw_text)
                )
            )

        doc.close()

        # Reject image-only or scanned PDFs without extractable text
        if total_characters == 0:
            document.status = DocumentStatus.FAILED
            document.processing_error = (
                "PDF contains no extractable text (scanned or image-only document). "
                "Optical Character Recognition (OCR) is not supported."
            )
            document.save(update_fields=['status', 'processing_error', 'updated_at'])
            return False

        # Atomic commit of page records and status transition to READY
        with transaction.atomic():
            # Clear any previously extracted pages for this document (e.g. on re-processing)
            document.pages.all().delete()
            DocumentPage.objects.bulk_create(pages_to_create)

            document.page_count = total_pages
            document.status = DocumentStatus.READY
            document.processing_error = ""
            document.save(update_fields=['page_count', 'status', 'processing_error', 'updated_at'])

        return True

    except Exception as exc:
        document.status = DocumentStatus.FAILED
        document.processing_error = f"Extraction failed: {str(exc)}"
        # Clean up partial page records on failure
        document.pages.all().delete()
        document.save(update_fields=['status', 'processing_error', 'updated_at'])
        return False


def can_user_access_document(user, document: Document) -> bool:
    """
    Evaluates whether a user is authorized to view or download a document.
    Reuses centralized machine authorization rules.
    """
    if not user or not user.is_authenticated or not user.is_active:
        return False

    if user.role == UserRole.ADMIN:
        return True

    if not document.is_active:
        return False

    return can_user_access_machine(user, document.machine)


def get_accessible_documents_queryset(user, machine_id=None):
    """
    Returns Document QuerySet scoped by user role and machine access permissions.
    """
    if not user or not user.is_authenticated or not user.is_active:
        return Document.objects.none()

    accessible_machines = get_accessible_machines_queryset(user)

    if user.role == UserRole.ADMIN:
        qs = Document.objects.all()
    elif user.role == UserRole.SUPERVISOR:
        qs = Document.objects.filter(machine__in=accessible_machines, is_active=True)
    elif user.role == UserRole.ENGINEER:
        from rag.models import IndexingStatus
        qs = Document.objects.filter(
            machine__in=accessible_machines,
            machine__status='ACTIVE',
            is_active=True,
            status=DocumentStatus.READY
        ).exclude(
            index_record__status__in=[IndexingStatus.FAILED, IndexingStatus.PROCESSING]
        )
    else:
        return Document.objects.none()

    if machine_id:
        qs = qs.filter(machine_id=machine_id)

    return qs.select_related('machine', 'uploaded_by')
