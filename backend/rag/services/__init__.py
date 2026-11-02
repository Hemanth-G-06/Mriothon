"""
Service layer for RAG operations.
Handles chunking, embedding generation, ChromaDB vector storage, and indexing lifecycle.
"""

from .chunking_service import ChunkingService, ChunkData
from .chroma_service import ChromaService, ChromaModelMismatchError
from .indexing_service import (
    DocumentIndexingService,
    DocumentIndexingError,
    DocumentNotReadyForIndexingError,
)

__all__ = [
    'ChunkingService',
    'ChunkData',
    'ChromaService',
    'ChromaModelMismatchError',
    'DocumentIndexingService',
    'DocumentIndexingError',
    'DocumentNotReadyForIndexingError',
]

