"""
ChromaDB integration service for vector storage and retrieval.
Manages persistent local ChromaDB client, collections with cosine similarity,
metadata-enriched vector insertion, deterministic vector IDs, and machine isolation.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
import chromadb
from chromadb.api.models.Collection import Collection
from django.conf import settings


class ChromaModelMismatchError(Exception):
    """Raised when an active ChromaDB collection was initialized with a different embedding model."""
    pass


class ChromaService:
    """
    Encapsulates interaction with ChromaDB vector database.
    Embeddings are strictly stored here, never in Neon PostgreSQL.
    """

    def __init__(
        self,
        persist_directory: Optional[Path] = None,
        collection_name: Optional[str] = None,
    ):
        raw_dir = persist_directory or getattr(
            settings, 'CHROMA_PERSIST_DIRECTORY', Path(settings.BASE_DIR) / 'data' / 'chroma'
        )
        self.persist_dir = Path(raw_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.collection_name = collection_name or getattr(
            settings, 'CHROMA_COLLECTION_NAME', 'manufacturing_manual_chunks_v1'
        )

        self._client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[Collection] = None

    @property
    def client(self) -> chromadb.PersistentClient:
        """Lazily instantiates the persistent ChromaDB client."""
        if self._client is None:
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        return self._client

    @staticmethod
    def generate_vector_id(document_id: str, page_number: int, chunk_index: int) -> str:
        """
        Generates a stable, deterministic vector ID to prevent duplicate vectors.
        Format: doc_{document_id}_p{page_number}_c{chunk_index}
        """
        return f"doc_{document_id}_p{page_number}_c{chunk_index}"

    def get_or_create_collection(self, embedding_model: Optional[str] = None) -> Collection:
        """
        Retrieves or creates the target collection with cosine similarity.
        Validates that the collection's registered embedding model matches to prevent vector space mixing.
        """
        collection_metadata = {
            "hnsw:space": "cosine",
            "description": "Manufacturing Manual Assistant document chunks",
        }
        if embedding_model:
            collection_metadata["embedding_model"] = embedding_model

        try:
            collection = self.client.get_collection(name=self.collection_name)
            
            # Check model consistency
            existing_model = (collection.metadata or {}).get("embedding_model")
            if embedding_model and existing_model and existing_model != embedding_model:
                raise ChromaModelMismatchError(
                    f"Collection '{self.collection_name}' was indexed with embedding model '{existing_model}', "
                    f"but current model is '{embedding_model}'. "
                    f"Mixing embeddings from different models in the same collection is prohibited. "
                    f"Rebuild collection or configure a distinct CHROMA_COLLECTION_NAME."
                )
            self._collection = collection
            return collection

        except Exception as e:
            if isinstance(e, ChromaModelMismatchError):
                raise
            # Collection does not exist; create it
            self._collection = self.client.create_collection(
                name=self.collection_name,
                metadata=collection_metadata
            )
            return self._collection

    def upsert_chunks(
        self,
        chunk_records: List[Dict],
        embedding_model: str,
    ) -> int:
        """
        Persists chunks and their embeddings into ChromaDB with metadata.

        chunk_records format:
        [
            {
                "id": "vector_id",
                "text": "chunk text",
                "embedding": [0.1, ...],
                "metadata": {
                    "document_id": "uuid",
                    "machine_id": "uuid",
                    "document_page_id": 12,
                    "page_number": 1,
                    "chunk_index": 0,
                    "embedding_model": "...",
                }
            },
            ...
        ]
        """
        if not chunk_records:
            return 0

        collection = self.get_or_create_collection(embedding_model=embedding_model)

        ids = [item["id"] for item in chunk_records]
        embeddings = [item["embedding"] for item in chunk_records]
        documents = [item["text"] for item in chunk_records]
        metadatas = [item["metadata"] for item in chunk_records]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        return len(ids)

    def delete_document_vectors(self, document_id: str) -> None:
        """
        Deletes all vector embeddings associated with a given document.
        Ensures clean, idempotent re-indexing and safe document deletion.
        """
        try:
            collection = self.get_or_create_collection()
            collection.delete(where={"document_id": str(document_id)})
        except Exception:
            # If collection is empty or not yet created, delete is a no-op
            pass

    def delete_machine_vectors(self, machine_id: str) -> None:
        """
        Deletes all vector embeddings associated with a given machine.
        Ensures clean, isolated vector cleanup when a test machine is deleted.
        """
        try:
            collection = self.get_or_create_collection()
            collection.delete(where={"machine_id": str(machine_id)})
        except Exception:
            # If collection is empty or not yet created, delete is a no-op
            pass

    def count_document_vectors(self, document_id: str) -> int:
        """
        Counts the number of vector embeddings currently present for a document.
        """
        try:
            collection = self.get_or_create_collection()
            results = collection.get(
                where={"document_id": str(document_id)},
                include=[]
            )
            return len(results.get("ids", []))
        except Exception:
            return 0

