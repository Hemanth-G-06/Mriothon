"""
Base classes and exceptions for the Embedding Provider architecture.
Ensures provider independence across hosted Hugging Face and local LM Studio providers.
"""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProviderError(Exception):
    """Base exception for all embedding provider errors."""
    pass


class EmbeddingConfigurationError(EmbeddingProviderError):
    """Raised when an embedding provider is misconfigured or missing credentials."""
    pass


class EmbeddingAuthenticationError(EmbeddingProviderError):
    """Raised when API credentials for the embedding provider are invalid or unauthorized."""
    pass


class EmbeddingRateLimitError(EmbeddingProviderError):
    """Raised when an external embedding provider rate limits requests (HTTP 429)."""
    pass


class EmbeddingTimeoutError(EmbeddingProviderError):
    """Raised when embedding generation times out."""
    pass


class EmbeddingDimensionMismatchError(EmbeddingProviderError):
    """Raised when returned vector dimensionality does not match the provider specification."""
    pass


class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for all embedding providers.
    Supports both single text and batch embedding generation with dimension validation.
    """

    def __init__(self, model_identifier: str, timeout: int = 30, expected_dimension: int = None):
        self.model_identifier = model_identifier.strip()
        self.timeout = timeout
        self.expected_dimension = expected_dimension

    def get_model_identifier(self) -> str:
        """Returns the canonical model identifier string."""
        return self.model_identifier

    def get_dimension(self) -> int:
        """Returns the expected output dimensionality for this embedding model."""
        return self.expected_dimension

    def validate_embedding(self, embedding: List[float]) -> List[float]:
        """
        Validates the structure and dimensionality of a single embedding vector.
        """
        if not isinstance(embedding, list) or not embedding:
            raise EmbeddingProviderError(f"Embedding must be a non-empty list of floats, got: {type(embedding)}")

        if self.expected_dimension is not None and len(embedding) != self.expected_dimension:
            raise EmbeddingDimensionMismatchError(
                f"Model '{self.model_identifier}' produced {len(embedding)} dimensions; "
                f"expected {self.expected_dimension} dimensions."
            )

        return embedding

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generates an embedding vector for a single text chunk."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a batch of text chunks."""
        pass

