"""
Management command: invalidate_chroma_embeddings

Sets DocumentIndex.status = FAILED (with explanation) and DocumentChunk.embedding = NULL
for all existing documents, preparing them for pgvector re-indexing.

Does NOT delete any Document, DocumentPage, DocumentChunk, Machine, User, or assignment.
Does NOT touch ChromaDB — the ChromaDB data directory remains intact as a fallback.

Safe to run multiple times (idempotent).
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from rag.models import DocumentChunk, DocumentIndex, IndexingStatus


class Command(BaseCommand):
    help = (
        "Invalidates ChromaDB-backed index records and clears pgvector embedding column "
        "to prepare for full pgvector re-indexing. Safe to re-run (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without modifying the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        prefix = "[DRY RUN] " if dry_run else ""

        self.stdout.write(f"\n{prefix}=== Phase 3: Invalidate ChromaDB Embeddings ===\n")

        # Count existing state
        total_indexes = DocumentIndex.objects.count()
        already_failed = DocumentIndex.objects.filter(
            status=IndexingStatus.FAILED,
            error_message__startswith="Invalidated:"
        ).count()
        total_chunks = DocumentChunk.objects.count()
        chunks_with_embedding = DocumentChunk.objects.filter(
            embedding__isnull=False
        ).count()

        self.stdout.write(f"  DocumentIndex records: {total_indexes}")
        self.stdout.write(f"  Already invalidated:   {already_failed}")
        self.stdout.write(f"  DocumentChunk rows:    {total_chunks}")
        self.stdout.write(f"  Chunks with pgvector:  {chunks_with_embedding}")

        if dry_run:
            self.stdout.write(
                f"\n[DRY RUN] Would set {total_indexes - already_failed} index record(s) to FAILED "
                f"and clear {chunks_with_embedding} embedding column(s)."
            )
            return

        invalidation_message = (
            "Invalidated: ChromaDB embeddings superseded by pgvector rebuild. "
            "Re-trigger indexing to generate pgvector embeddings."
        )

        with transaction.atomic():
            # 1. Mark all DocumentIndex records as FAILED
            updated_indexes = DocumentIndex.objects.exclude(
                status=IndexingStatus.FAILED,
                error_message__startswith="Invalidated:"
            ).update(
                status=IndexingStatus.FAILED,
                error_message=invalidation_message,
                updated_at=timezone.now(),
            )

            # 2. Clear pgvector embedding column for all chunks
            # (Most are NULL anyway before first pgvector indexing, but clear idempotently)
            updated_chunks = DocumentChunk.objects.filter(
                embedding__isnull=False
            ).update(
                embedding=None,
                embedding_updated_at=None,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n[DONE] Invalidated {updated_indexes} DocumentIndex record(s).\n"
                f"       Cleared {updated_chunks} pgvector embedding(s) from DocumentChunk.\n"
                f"       ChromaDB data directory NOT modified.\n"
                f"\nNext step: re-upload or re-trigger indexing via the Admin UI "
                f"with VECTOR_BACKEND=pgvector to rebuild the knowledge base.\n"
            )
        )

