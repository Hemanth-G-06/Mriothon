"""
Document Indexing Lifecycle Service.
Coordinates text chunking, embedding generation, relational metadata storage in Neon,
and vector indexing. When VECTOR_BACKEND='pgvector', embeddings are written directly
to the document_chunks.embedding column. When VECTOR_BACKEND='chroma', the legacy
ChromaDB path is used.
"""

import logging
from typing import Optional
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from documents.models import Document, DocumentStatus
from rag.models import DocumentChunk, DocumentIndex, IndexingStatus
from .chunking_service import ChunkingService
from .chroma_service import ChromaService
from .providers.base import BaseEmbeddingProvider, EmbeddingProviderError
from .providers.factory import get_embedding_provider

logger = logging.getLogger(__name__)


class DocumentIndexingError(Exception):
    """Base exception for document indexing failures."""
    pass


class DocumentNotReadyForIndexingError(DocumentIndexingError):
    """Raised when a document is requested for indexing before completing PDF extraction."""
    pass


class DocumentIndexingService:
    """
    Orchestrates the document indexing lifecycle across Neon PostgreSQL and ChromaDB.
    """

    def __init__(
        self,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        chunking_service: Optional[ChunkingService] = None,
        chroma_service: Optional[ChromaService] = None,
        vector_backend: Optional[str] = None,
    ):
        self.embedding_provider = embedding_provider
        self.chunking_service = chunking_service or ChunkingService()
        self._explicit_chroma_service = chroma_service is not None
        self._chroma_service = chroma_service
        self._explicit_vector_backend = vector_backend

    @property
    def chroma_service(self) -> ChromaService:
        if self._chroma_service is None:
            self._chroma_service = ChromaService()
        return self._chroma_service

    def _resolve_vector_backend(self) -> str:
        if self._explicit_vector_backend:
            return self._explicit_vector_backend
        if self._explicit_chroma_service:
            return 'chroma'
        return getattr(settings, 'VECTOR_BACKEND', 'pgvector')

    def _get_provider(self) -> BaseEmbeddingProvider:
        """Lazily obtains the configured embedding provider if not explicitly injected."""
        if self.embedding_provider is None:
            self.embedding_provider = get_embedding_provider()
        return self.embedding_provider

    def index_document(self, document: Document, force: bool = False) -> DocumentIndex:
        """
        Executes the full indexing workflow for a Document:
        1. Validate eligibility (must be active and PDF extraction must be READY).
        2. Chunk extracted text page by page.
        3. Generate embeddings via configured provider.
        4. Persist chunk records in Neon PostgreSQL.
        5a. (VECTOR_BACKEND='pgvector') Write embeddings into document_chunks.embedding column.
        5b. (VECTOR_BACKEND='chroma') Persist vectors and metadata in ChromaDB.
        6. Verify vector presence.
        7. Update DocumentIndex status to READY.
        """
        vector_backend = self._resolve_vector_backend()
        if not document.is_active:
            raise DocumentIndexingError(f"Cannot index inactive document {document.id}.")

        if document.status != DocumentStatus.READY:
            raise DocumentNotReadyForIndexingError(
                f"Document '{document.title}' ({document.id}) has status '{document.status}'. "
                f"Indexing requires PDF extraction to be completed (status: READY)."
            )

        # Get or create DocumentIndex tracker
        index_record, _ = DocumentIndex.objects.get_or_create(document=document)
        index_record.status = IndexingStatus.PROCESSING
        index_record.error_message = ''
        index_record.save(update_fields=['status', 'error_message', 'updated_at'])

        try:
            provider = self._get_provider()
            model_id = provider.get_model_identifier()

            # 1. Chunk document pages
            chunks = self.chunking_service.chunk_document(document)
            if not chunks:
                index_record.status = IndexingStatus.FAILED
                index_record.error_message = (
                    "Document contains no extractable text chunks across any page. "
                    "Verify PDF extraction output."
                )
                index_record.save(update_fields=['status', 'error_message', 'updated_at'])
                return index_record

            chunk_texts = [c.text for c in chunks]

            # 2. Generate embeddings
            try:
                embeddings = provider.embed_batch(chunk_texts)
            except EmbeddingProviderError as e:
                logger.error("Embedding generation failed for document %s: %s", document.id, e)
                index_record.status = IndexingStatus.FAILED
                index_record.error_message = f"Embedding generation failed: {e}"
                index_record.save(update_fields=['status', 'error_message', 'updated_at'])
                raise DocumentIndexingError(f"Embedding generation failed: {e}") from e

            # 3. Prepare Neon and Chroma records
            chroma_records = []
            db_chunk_instances = []

            for chunk_data, emb in zip(chunks, embeddings):
                vector_id = ChromaService.generate_vector_id(
                    document_id=str(document.id),
                    page_number=chunk_data.page_number,
                    chunk_index=chunk_data.chunk_index,
                )

                # Build DocumentChunk instance — include embedding when using pgvector backend
                chunk_kwargs = dict(
                    document=document,
                    page_id=chunk_data.page_id,
                    chunk_index=chunk_data.chunk_index,
                    text=chunk_data.text,
                    token_count=chunk_data.token_count,
                    character_start_offset=chunk_data.character_start_offset,
                    character_end_offset=chunk_data.character_end_offset,
                    chroma_vector_id=vector_id,
                    embedding_model=model_id,
                )
                if vector_backend == 'pgvector':
                    chunk_kwargs['embedding'] = emb
                    chunk_kwargs['embedding_updated_at'] = timezone.now()

                db_chunk_instances.append(DocumentChunk(**chunk_kwargs))

                chroma_records.append({
                    "id": vector_id,
                    "text": chunk_data.text,
                    "embedding": emb,
                    "metadata": {
                        "document_id": str(document.id),
                        "machine_id": str(document.machine_id),
                        "document_page_id": chunk_data.page_id,
                        "page_number": chunk_data.page_number,
                        "chunk_index": chunk_data.chunk_index,
                        "embedding_model": model_id,
                    }
                })

            if vector_backend == 'pgvector':
                # 4 (pgvector path). Atomically persist chunks with embeddings in PostgreSQL only.
                with transaction.atomic():
                    DocumentChunk.objects.filter(document=document).delete()
                    DocumentChunk.objects.bulk_create(db_chunk_instances)

                # 5 (pgvector path). Verify expected chunk count.
                pg_count = DocumentChunk.objects.filter(
                    document=document, embedding__isnull=False
                ).count()
                if pg_count != len(chunks):
                    index_record.status = IndexingStatus.FAILED
                    index_record.error_message = (
                        f"pgvector chunk verification failed: expected {len(chunks)}, "
                        f"found {pg_count} with non-NULL embedding."
                    )
                    index_record.save(update_fields=['status', 'error_message', 'updated_at'])
                    raise DocumentIndexingError(index_record.error_message)

                logger.info(
                    "pgvector: persisted %d chunk embeddings for document %s.",
                    pg_count, document.id
                )
            else:
                # 4 (chroma path). Atomically persist DocumentChunk records in Neon.
                with transaction.atomic():
                    DocumentChunk.objects.filter(document=document).delete()
                    DocumentChunk.objects.bulk_create(db_chunk_instances)

                # 5 (chroma path). Persist vectors in ChromaDB.
                try:
                    self.chroma_service.delete_document_vectors(str(document.id))
                    self.chroma_service.upsert_chunks(
                        chunk_records=chroma_records,
                        embedding_model=model_id,
                    )
                except Exception as e:
                    logger.error("ChromaDB persistence failed for document %s: %s", document.id, e)
                    # Rollback Neon chunks on ChromaDB failure to avoid desynchronization
                    DocumentChunk.objects.filter(document=document).delete()
                    index_record.status = IndexingStatus.FAILED
                    index_record.error_message = f"Vector persistence in ChromaDB failed: {e}"
                    index_record.save(update_fields=['status', 'error_message', 'updated_at'])
                    raise DocumentIndexingError(f"ChromaDB persistence failed: {e}") from e

                # 6 (chroma path). Verify ChromaDB contains expected vector count.
                vector_count = self.chroma_service.count_document_vectors(str(document.id))
                if vector_count != len(chunks):
                    index_record.status = IndexingStatus.FAILED
                    index_record.error_message = (
                        f"Vector count verification failed: expected {len(chunks)} vectors, "
                        f"found {vector_count} in ChromaDB."
                    )
                    index_record.save(update_fields=['status', 'error_message', 'updated_at'])
                    raise DocumentIndexingError(index_record.error_message)

            # 7. Mark as READY
            index_record.status = IndexingStatus.READY
            index_record.chunk_count = len(chunks)
            index_record.embedding_model = model_id
            index_record.error_message = ''
            index_record.save(update_fields=['status', 'chunk_count', 'embedding_model', 'error_message', 'updated_at'])

            logger.info("Successfully indexed document %s with %d chunks.", document.id, len(chunks))
            return index_record

        except Exception as e:
            if not isinstance(e, DocumentIndexingError):
                logger.exception("Unexpected error during indexing of document %s: %s", document.id, e)
                index_record.status = IndexingStatus.FAILED
                index_record.error_message = f"Unexpected indexing error: {e}"
                index_record.save(update_fields=['status', 'error_message', 'updated_at'])
            raise

