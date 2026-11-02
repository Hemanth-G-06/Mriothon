"""
LM Studio local embedding provider using OpenAI-compatible HTTP endpoint.
Designed for local development and offline testing with Nomic Embed Text v1.5.
"""

import requests
from typing import List, Optional
from .base import (
    BaseEmbeddingProvider,
    EmbeddingConfigurationError,
    EmbeddingDimensionMismatchError,
    EmbeddingProviderError,
    EmbeddingTimeoutError,
)


class LMStudioEmbeddingProvider(BaseEmbeddingProvider):
    """
    Client for local LM Studio instance exposing an OpenAI-compatible /v1/embeddings endpoint.
    Default model: nomic-ai/nomic-embed-text-v1.5-GGUF (768 dimensions).
    Applies 'search_document: ' prefix specifically when using Nomic models.
    """

    DEFAULT_BASE_URL = 'http://127.0.0.1:1234/v1'
    DEFAULT_MODEL = 'nomic-ai/nomic-embed-text-v1.5-GGUF'
    NOMIC_DIMENSION = 768
    NOMIC_DOCUMENT_PREFIX = 'search_document: '
    NOMIC_QUERY_PREFIX = 'search_query: '

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_identifier: Optional[str] = None,
        timeout: int = 30,
        expected_dimension: Optional[int] = None,
    ):
        model = (model_identifier or self.DEFAULT_MODEL).strip()
        is_nomic = 'nomic' in model.lower()
        dim = expected_dimension if expected_dimension is not None else (
            self.NOMIC_DIMENSION if is_nomic else None
        )
        super().__init__(model_identifier=model, timeout=timeout, expected_dimension=dim)

        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip('/')
        self.endpoint = f"{self.base_url}/embeddings"
        self.is_nomic = is_nomic

    def _format_input(self, text: str) -> str:
        """
        Applies model-specific prefixing.
        Nomic Embed Text requires 'search_document: ' for indexed documents.
        """
        clean = text.strip()
        if self.is_nomic and not clean.startswith(self.NOMIC_DOCUMENT_PREFIX):
            return f"{self.NOMIC_DOCUMENT_PREFIX}{clean}"
        return clean

    def _format_query(self, text: str) -> str:
        """
        Applies model-specific query prefixing.
        Nomic Embed Text requires 'search_query: ' for search queries.
        """
        clean = text.strip()
        if self.is_nomic and not clean.startswith(self.NOMIC_QUERY_PREFIX):
            return f"{self.NOMIC_QUERY_PREFIX}{clean}"
        return clean

    def _execute_request(self, payload: dict) -> requests.Response:
        try:
            response = requests.post(
                self.endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout
            )
        except requests.exceptions.Timeout as e:
            raise EmbeddingTimeoutError(
                f"LM Studio local embedding request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise EmbeddingProviderError(
                f"Embedding service unavailable. Please ensure LM Studio is running with "
                f"{self.model_identifier} at {self.base_url} or configure an alternative embedding provider."
            ) from e
        except requests.exceptions.RequestException as e:
            raise EmbeddingProviderError(f"LM Studio request error: {e}") from e

        if not response.ok:
            raise EmbeddingProviderError(
                f"LM Studio returned HTTP {response.status_code}: {response.text[:300]}"
            )

        return response

    def embed_text(self, text: str) -> List[float]:
        """Generates embedding for a single text chunk."""
        if not text or not text.strip():
            raise EmbeddingProviderError("Cannot embed empty text.")

        formatted = self._format_input(text)
        payload = {
            "model": self.model_identifier,
            "input": formatted
        }
        response = self._execute_request(payload)
        data = response.json()

        try:
            embedding = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as e:
            raise EmbeddingProviderError(f"Malformed response from LM Studio: {data}") from e

        return self.validate_embedding(embedding)

    def embed_query(self, query: str) -> List[float]:
        """Generates embedding for a search query using search_query: prefix for Nomic."""
        if not query or not query.strip():
            raise EmbeddingProviderError("Cannot embed empty query.")

        formatted = self._format_query(query)
        payload = {
            "model": self.model_identifier,
            "input": formatted
        }
        response = self._execute_request(payload)
        data = response.json()

        try:
            embedding = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as e:
            raise EmbeddingProviderError(f"Malformed response from LM Studio: {data}") from e

        return self.validate_embedding(embedding)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of text chunks."""
        if not texts:
            return []

        cleaned_texts = [t.strip() for t in texts if t and t.strip()]
        if not cleaned_texts:
            raise EmbeddingProviderError("All texts in batch are empty.")

        formatted_inputs = [self._format_input(t) for t in cleaned_texts]
        payload = {
            "model": self.model_identifier,
            "input": formatted_inputs
        }
        response = self._execute_request(payload)
        data = response.json()

        try:
            # Sort embeddings by index to guarantee input ordering
            sorted_items = sorted(data["data"], key=lambda item: item.get("index", 0))
            embeddings = [item["embedding"] for item in sorted_items]
        except (KeyError, TypeError) as e:
            raise EmbeddingProviderError(f"Malformed batch response from LM Studio: {data}") from e

        if len(embeddings) != len(formatted_inputs):
            raise EmbeddingProviderError(
                f"LM Studio returned {len(embeddings)} embeddings for {len(formatted_inputs)} inputs."
            )

        return [self.validate_embedding(emb) for emb in embeddings]

