"""
pgvector Retrieval Service for RAG pipeline.
Executes machine-isolated cosine-distance search in PostgreSQL (pgvector)
and returns RetrievedChunkContext instances compatible with the existing pipeline.

This module is only invoked when settings.VECTOR_BACKEND == 'pgvector'.
"""

import logging
from typing import List, Optional
import uuid

from django.conf import settings
from django.utils import timezone

from machines.models import Machine, MachineStatus
from machines.services import can_user_access_machine
from rag.models import DocumentChunk, IndexingStatus
from documents.models import DocumentStatus
from .providers.base import BaseEmbeddingProvider
from .providers.factory import get_embedding_provider
from .retrieval_service import (
    RetrievedChunkContext,
    RetrievalError,
    MachineNotFoundError,
    MachineInactiveError,
    MachineAccessDeniedError,
    InvalidQueryError,
    SemanticRetrievalService,
)

logger = logging.getLogger(__name__)


class PgvectorRetrievalService:
    """
    Cosine-distance vector retrieval from PostgreSQL via pgvector.
    Enforces machine-level isolation and active-document filtering identically
    to SemanticRetrievalService (ChromaDB path).
    """

    def __init__(
        self,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        top_k: Optional[int] = None,
    ):
        self.embedding_provider = embedding_provider
        self.top_k = top_k or getattr(settings, 'RAG_TOP_K', 5)

    def _get_provider(self) -> BaseEmbeddingProvider:
        if self.embedding_provider is None:
            self.embedding_provider = get_embedding_provider()
        return self.embedding_provider

    def retrieve_context(
        self,
        user,
        machine_id: str,
        question: str,
        top_k: Optional[int] = None,
    ) -> List[RetrievedChunkContext]:
        """
        Executes machine-isolated pgvector retrieval:
        1. Validates machine existence and active status.
        2. Validates user access to the machine.
        3. Generates embedding for the search question.
        4. Queries DocumentChunk.embedding via pgvector cosine distance,
           filtered to the specified machine's READY documents.
        5. Returns ranked RetrievedChunkContext list.
        """
        clean_question = (question or '').strip()
        if not clean_question:
            raise InvalidQueryError("The search question cannot be empty.")

        # 1. Validate machine existence & status
        try:
            machine_uuid = uuid.UUID(str(machine_id))
        except (ValueError, AttributeError):
            raise MachineNotFoundError(f"Invalid machine UUID: '{machine_id}'")

        try:
            machine = Machine.objects.get(id=machine_uuid)
        except Machine.DoesNotExist:
            raise MachineNotFoundError(f"Machine '{machine_id}' does not exist.")

        if machine.status != MachineStatus.ACTIVE:
            raise MachineInactiveError(
                f"Machine '{machine.name}' ({machine.machine_code}) is inactive."
            )

        # 2. Validate user access
        if not can_user_access_machine(user, machine):
            raise MachineAccessDeniedError(
                f"User does not have authorization to access machine '{machine.machine_code}'."
            )

        limit = top_k or self.top_k
        provider = self._get_provider()

        # 3. Generate query embedding
        query_vector = provider.embed_query(clean_question)

        # 4. pgvector cosine-distance search, filtered to machine's READY documents
        # Import here to avoid module-level import when VECTOR_BACKEND=chroma
        from pgvector.django import CosineDistance

        try:
            chunks_with_dist = list(
                DocumentChunk.objects
                .filter(
                    document__machine=machine,
                    document__is_active=True,
                    document__status=DocumentStatus.READY,
                    document__index_record__status=IndexingStatus.READY,
                    embedding__isnull=False,
                )
                .select_related('document', 'page')
                .annotate(dist=CosineDistance('embedding', query_vector))
                .order_by('dist')
                [:limit]
            )
        except Exception as e:
            raise RetrievalError(f"pgvector retrieval failed: {e}") from e

        # 5. Build structured context list
        retrieved_contexts: List[RetrievedChunkContext] = []
        for chunk in chunks_with_dist:
            canonical_page = chunk.page.page_number
            source_id = SemanticRetrievalService.format_source_id(
                document_id=str(chunk.document.id),
                page_number=canonical_page,
                chunk_index=chunk.chunk_index,
            )
            distance = float(chunk.dist)
            score = round(max(0.0, 1.0 - distance), 4)

            retrieved_contexts.append(
                RetrievedChunkContext(
                    source_id=source_id,
                    document_id=str(chunk.document.id),
                    document_title=chunk.document.title,
                    original_filename=chunk.document.original_filename,
                    machine_id=str(machine.id),
                    page_number=canonical_page,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.text,
                    similarity_score=score,
                    chroma_vector_id=chunk.chroma_vector_id,  # preserved for PDF citation URL
                )
            )

        logger.debug(
            "pgvector retrieved %d chunks for machine %s (top_k=%d)",
            len(retrieved_contexts), machine_id, limit
        )
        return retrieved_contexts

