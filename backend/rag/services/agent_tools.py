"""
Controlled Backend Tools for Agentic AI Orchestration.
Enforces strict machine isolation, role-based authorization,
and controlled access to relational database and vector retrieval services.
Agents NEVER receive raw database or SQL access.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import uuid

from django.core.exceptions import PermissionDenied

from accounts.models import UserRole
from documents.models import Document, DocumentPage, DocumentStatus
from history.models import QueryRecord
from machines.models import Machine, MachineStatus
from machines.services import can_user_access_machine
from rag.models import DocumentChunk
from rag.services.retrieval_service import (
    SemanticRetrievalService,
    RetrievedChunkContext,
    MachineNotFoundError,
    MachineInactiveError,
    MachineAccessDeniedError,
    get_retrieval_service,
)

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    revision: str
    page_number: int
    text: str
    score: float
    retrieval_method: str
    machine_id: str
    machine_code: str


class AgentTools:
    """
    Controlled tool suite exposed to LangGraph agent nodes.
    Each method validates inputs, checks user permissions, and bounds execution.
    """

    def __init__(self, retrieval_service=None):
        self.retrieval_service = retrieval_service or get_retrieval_service()

    def get_machine_context(self, machine_id: str, user: Any) -> Dict[str, Any]:
        """
        Tool: Get selected machine context.
        Verifies active status and user assignment.
        """
        try:
            machine_uuid = uuid.UUID(str(machine_id))
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid machine ID format: {machine_id}")

        try:
            machine = Machine.objects.get(id=machine_uuid)
        except Machine.DoesNotExist:
            raise MachineNotFoundError(f"Machine '{machine_id}' does not exist.")

        if machine.status != MachineStatus.ACTIVE:
            raise MachineInactiveError(f"Machine '{machine.machine_code}' is currently inactive.")

        if not can_user_access_machine(user, machine):
            raise MachineAccessDeniedError(
                f"User does not have authorization to access machine '{machine.machine_code}'."
            )

        active_docs_count = Document.objects.filter(
            machine=machine,
            is_active=True,
            status=DocumentStatus.READY
        ).count()

        return {
            'machine_id': str(machine.id),
            'machine_code': machine.machine_code,
            'machine_name': machine.name,
            'manufacturer': machine.manufacturer,
            'model_number': machine.model_number,
            'status': machine.status,
            'active_documents_count': active_docs_count,
        }

    def retrieve_manual_passages(
        self,
        machine_id: str,
        user: Any,
        query: str,
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """
        Tool: Retrieve manual passages.
        Executes semantic retrieval with mandatory backend-enforced machine-ID filtering.
        Resolves chunks against Neon PostgreSQL records.
        """
        raw_chunks: List[RetrievedChunkContext] = self.retrieval_service.retrieve_context(
            user=user,
            machine_id=str(machine_id),
            question=query,
        )

        retrieved: List[RetrievedChunk] = []
        for c in raw_chunks[:top_k]:
            retrieved.append(
                RetrievedChunk(
                    chunk_id=c.source_id,
                    document_id=c.document_id,
                    document_title=c.document_title,
                    revision='1.0',
                    page_number=c.page_number,
                    text=c.chunk_text,
                    score=c.similarity_score,
                    retrieval_method='vector',
                    machine_id=c.machine_id,
                    machine_code='',
                )
            )

        return retrieved

    def resolve_document_page_info(
        self,
        document_id: str,
        page_number: int,
        machine_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Tool: Resolve document and page information.
        Confirms document existence, active state, READY status, and page existence in PostgreSQL.
        """
        try:
            doc = Document.objects.get(id=document_id, is_active=True)
            if str(doc.machine_id) != str(machine_id):
                return None
            if doc.status not in (DocumentStatus.READY, 'APPROVED'):
                return None
            page = DocumentPage.objects.filter(document=doc, page_number=page_number).first()
            if not page:
                return None
            return {
                'document_id': str(doc.id),
                'document_title': doc.title,
                'page_number': page.page_number,
                'char_count': getattr(page, 'character_count', 0),
            }
        except Exception:
            return None

    def get_permitted_query_history(
        self,
        machine_id: str,
        user: Any,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Tool: Retrieve permitted historical query context.
        Engineers see only their own queries; supervisors/admins see all queries for the machine.
        """
        qs = QueryRecord.objects.filter(machine_id=machine_id)
        if getattr(user, 'role', None) == UserRole.ENGINEER:
            qs = qs.filter(user=user)

        recent = qs.order_by('-created_at')[:limit]
        return [
            {
                'id': str(q.id),
                'question': q.question,
                'answer': q.answer[:200],
                'abstained': q.abstained,
                'created_at': q.created_at.isoformat(),
            }
            for q in recent
        ]
