"""
Administrative management command to index or re-index manufacturing manuals into ChromaDB.
"""

from django.core.management.base import BaseCommand, CommandError
from documents.models import Document, DocumentStatus
from rag.services.indexing_service import (
    DocumentIndexingService,
    DocumentIndexingError,
    DocumentNotReadyForIndexingError,
)


class Command(BaseCommand):
    help = "Re-indexes active, extracted technical manuals into Neon PostgreSQL and ChromaDB."

    def add_arguments(self, parser):
        parser.add_argument(
            '--document-id',
            type=str,
            help="UUID of a specific document to re-index."
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help="Re-index all active documents that have completed PDF extraction."
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help="Bypass interactive confirmation prompt."
        )

    def handle(self, *args, **options):
        doc_id = options.get('document_id')
        reindex_all = options.get('all')
        force = options.get('force')

        if not doc_id and not reindex_all:
            raise CommandError("Please specify either --document-id <UUID> or --all.")

        if doc_id and reindex_all:
            raise CommandError("Cannot combine --document-id and --all. Choose one.")

        if doc_id:
            try:
                documents = [Document.objects.get(id=doc_id, is_active=True)]
            except Document.DoesNotExist:
                raise CommandError(f"Active document with ID '{doc_id}' not found.")
        else:
            documents = list(
                Document.objects.filter(
                    is_active=True,
                    status=DocumentStatus.READY
                ).order_by('created_at')
            )
            if not documents:
                self.stdout.write(self.style.WARNING("No eligible documents with status 'READY' found for indexing."))
                return

        if not force:
            count = len(documents)
            confirm_msg = (
                f"You are about to re-index {count} document(s). "
                f"Existing vector embeddings and chunk metadata will be regenerated. Proceed? [y/N]: "
            )
            try:
                confirmation = input(confirm_msg).strip().lower()
                if confirmation not in ('y', 'yes'):
                    self.stdout.write(self.style.WARNING("Operation cancelled by user."))
                    return
            except (EOFError, KeyboardInterrupt):
                self.stdout.write(self.style.WARNING("\nOperation cancelled."))
                return

        indexing_service = DocumentIndexingService()
        success_count = 0
        failure_count = 0

        self.stdout.write(f"Starting indexing for {len(documents)} document(s)...")

        for doc in documents:
            self.stdout.write(f"-> Processing '{doc.title}' ({doc.id})...", ending=" ")
            try:
                index_record = indexing_service.index_document(doc, force=force)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"DONE ({index_record.chunk_count} chunks indexed using '{index_record.embedding_model}')"
                    )
                )
                success_count += 1
            except DocumentNotReadyForIndexingError as e:
                self.stdout.write(self.style.ERROR(f"SKIPPED ({e})"))
                failure_count += 1
            except DocumentIndexingError as e:
                self.stdout.write(self.style.ERROR(f"FAILED ({e})"))
                failure_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"UNEXPECTED ERROR ({e})"))
                failure_count += 1

        self.stdout.write("\n--- Indexing Summary ---")
        self.stdout.write(self.style.SUCCESS(f"Successfully indexed: {success_count}"))
        if failure_count > 0:
            self.stdout.write(self.style.ERROR(f"Failed / Skipped: {failure_count}"))
        else:
            self.stdout.write(self.style.SUCCESS("All requested documents indexed without errors."))

