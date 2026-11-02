"""
Service layer for RAG and Agentic AI operations.
Handles chunking, embedding generation, ChromaDB vector storage, pgvector storage,
indexing lifecycle, semantic retrieval, Gemini answer generation, evidence gating,
and LangGraph multi-agent orchestration.
"""

from .chunking_service import ChunkingService, ChunkData
from .chroma_service import ChromaService, ChromaModelMismatchError
from .indexing_service import (
    DocumentIndexingService,
    DocumentIndexingError,
    DocumentNotReadyForIndexingError,
)
from .retrieval_service import (
    SemanticRetrievalService,
    RetrievedChunkContext,
    RetrievalError,
    MachineNotFoundError,
    MachineInactiveError,
    MachineAccessDeniedError,
    InvalidQueryError,
    get_retrieval_service,
)
from .generation_service import (
    GroundedAnswerGenerationService,
    GroundedAnswer,
    VerifiedCitation,
    EXACT_ABSTENTION_MESSAGE,
)
from .agent_tools import AgentTools, RetrievedChunk
from .evidence_gate_service import (
    EvidenceGateService,
    EvidenceEvaluationResult,
    CitationValidator,
    CitationValidationResult,
)
from .langgraph_agent_service import IndustriaXAgentWorkflow, AgentState

__all__ = [
    'ChunkingService',
    'ChunkData',
    'ChromaService',
    'ChromaModelMismatchError',
    'DocumentIndexingService',
    'DocumentIndexingError',
    'DocumentNotReadyForIndexingError',
    'SemanticRetrievalService',
    'RetrievedChunkContext',
    'RetrievalError',
    'MachineNotFoundError',
    'MachineInactiveError',
    'MachineAccessDeniedError',
    'InvalidQueryError',
    'get_retrieval_service',
    'GroundedAnswerGenerationService',
    'GroundedAnswer',
    'VerifiedCitation',
    'EXACT_ABSTENTION_MESSAGE',
    'AgentTools',
    'RetrievedChunk',
    'EvidenceGateService',
    'EvidenceEvaluationResult',
    'CitationValidator',
    'CitationValidationResult',
    'IndustriaXAgentWorkflow',
    'AgentState',
]
