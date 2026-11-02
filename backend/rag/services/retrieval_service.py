import logging
logger = logging.getLogger(__name__)
"""
Semantic Retrieval Service for RAG pipeline.
Executes machine-isolated vector search in ChromaDB and resolves verified chunk
records, titles, and page citations directly from Neon PostgreSQL.
"""

from dataclasses import dataclass
from typing import List, Optional
import uuid

from django.conf import settings

from machines.models import Machine, MachineStatus
from machines.services import can_user_access_machine
from rag.models import DocumentChunk
from .chroma_service import ChromaService
from .providers.base import BaseEmbeddingProvider
from .providers.factory import get_embedding_provider


class RetrievalError(Exception):
    """Base exception for retrieval errors."""
    pass


class MachineNotFoundError(RetrievalError):
    """Raised when the specified machine does not exist."""
    pass


class MachineInactiveError(RetrievalError):
    """Raised when attempting to query an inactive machine."""
    pass


class MachineAccessDeniedError(RetrievalError):
    """Raised when the user is not authorized to query the specified machine."""
    pass


class InvalidQueryError(RetrievalError):
    """Raised when the user submits an empty or invalid question."""
    pass


@dataclass
class RetrievedChunkContext:
    """
    Structured context of a single verified chunk retrieved for LLM prompt grounding.
    """
    source_id: str
    document_id: str
    document_title: str
    original_filename: str
    machine_id: str
    page_number: int
    chunk_index: int
    chunk_text: str
    similarity_score: float
    chroma_vector_id: str


class SemanticRetrievalService:
    """
    Coordinates semantic vector retrieval filtered strictly by machine_id,
    and resolves relational domain data from Neon PostgreSQL.
    """

    def __init__(
        self,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        chroma_service: Optional[ChromaService] = None,
        top_k: Optional[int] = None,
    ):
        self.embedding_provider = embedding_provider
        self.chroma_service = chroma_service or ChromaService()
        self.top_k = top_k or getattr(settings, 'RAG_TOP_K', 5)

    def _get_provider(self) -> BaseEmbeddingProvider:
        if self.embedding_provider is None:
            self.embedding_provider = get_embedding_provider()
        return self.embedding_provider

    @staticmethod
    def format_source_id(document_id: str, page_number: int, chunk_index: int) -> str:
        """
        Creates a clean, human-readable source ID for LLM prompt grounding and citation tracking.
        e.g. DOC-9B1DEB-P3-C0
        """
        clean_uuid = str(document_id).replace('-', '')[:6].upper()
        return f"DOC-{clean_uuid}-P{page_number}-C{chunk_index}"

    def retrieve_context(
        self,
        user,
        machine_id: str,
        question: str,
        top_k: Optional[int] = None,
    ) -> List[RetrievedChunkContext]:
        """
        Executes machine-isolated retrieval:
        1. Validates machine existence and active status.
        2. Validates user access to the machine.
        3. Generates embedding for the search question.
        4. Queries ChromaDB applying a mandatory `where={'machine_id': machine_id}` filter.
        5. Resolves matching chunk records from Neon PostgreSQL to verify active document status.
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
            raise MachineInactiveError(f"Machine '{machine.name}' ({machine.machine_code}) is inactive.")

        # 2. Validate user access
        if not can_user_access_machine(user, machine):
            raise MachineAccessDeniedError(
                f"User does not have authorization to access machine '{machine.machine_code}'."
            )

        limit = top_k or self.top_k
        provider = self._get_provider()
        model_id = provider.get_model_identifier()

        # 3. Generate query embedding
        query_vector = provider.embed_query(clean_question)

        # 4. Query ChromaDB with mandatory machine-level isolation
        collection = self.chroma_service.get_or_create_collection(embedding_model=model_id)

        try:
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=limit,
                where={"machine_id": str(machine.id)},  # Strict isolation at vector index level
                include=["metadatas", "documents", "distances"]
            )
        except Exception as e:
            raise RetrievalError(f"ChromaDB retrieval failed: {e}") from e

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        retrieved_ids = results["ids"][0]
        distances = results.get("distances", [[]])[0] if results.get("distances") else [0.0] * len(retrieved_ids)
        metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else [{}] * len(retrieved_ids)

        # 5. Resolve retrieved chunks from Neon PostgreSQL
        db_chunks = DocumentChunk.objects.filter(
            chroma_vector_id__in=retrieved_ids,
            document__machine=machine,
            document__is_active=True
        ).select_related('document', 'page')

        chunk_lookup = {chunk.chroma_vector_id: chunk for chunk in db_chunks}

        # 6. Preserve similarity ranking and build structured context
        retrieved_contexts: List[RetrievedChunkContext] = []
        for v_id, dist, meta in zip(retrieved_ids, distances, metadatas):
            if v_id in chunk_lookup:
                chunk = chunk_lookup[v_id]
                canonical_page = chunk.page.page_number

                # Verify page number against ChromaDB metadata and enforce PostgreSQL authority
                chroma_page = meta.get("page_number") if isinstance(meta, dict) else None
                if chroma_page is not None and int(chroma_page) != int(canonical_page):
                    logger.warning(
                        "ChromaDB metadata page %s conflicts with PostgreSQL canonical page %s for chunk %s. "
                        "Using authoritative PostgreSQL page.",
                        chroma_page,
                        canonical_page,
                        v_id
                    )

                source_id = self.format_source_id(
                    document_id=str(chunk.document.id),
                    page_number=canonical_page,
                    chunk_index=chunk.chunk_index
                )
                score = round(max(0.0, 1.0 - float(dist)), 4)

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
                        chroma_vector_id=v_id,
                    )
                )

        return retrieved_contexts



def get_retrieval_service(
    embedding_provider=None,
    chroma_service=None,
    top_k: int = None,
):
    """
    Factory that returns the correct retrieval service based on settings.VECTOR_BACKEND.

    'chroma'   -> SemanticRetrievalService (ChromaDB-backed, legacy default)
    'pgvector' -> PgvectorRetrievalService (PostgreSQL cosine-distance, active path)
    """
    from django.conf import settings as _settings
    backend = getattr(_settings, 'VECTOR_BACKEND', 'pgvector')

    if backend == 'pgvector':
        from .pgvector_retrieval_service import PgvectorRetrievalService
        return PgvectorRetrievalService(
            embedding_provider=embedding_provider,
            top_k=top_k,
        )
    else:
        return SemanticRetrievalService(
            embedding_provider=embedding_provider,
            chroma_service=chroma_service,
            top_k=top_k,
        )
