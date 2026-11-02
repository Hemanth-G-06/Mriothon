"""
Hugging Face Inference Provider integration for hosted document embedding generation.
Supports Hugging Face Serverless Inference API and router endpoints with batch processing.
"""

import requests
from typing import List, Optional
from .base import (
    BaseEmbeddingProvider,
    EmbeddingAuthenticationError,
    EmbeddingConfigurationError,
    EmbeddingDimensionMismatchError,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
)


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    """
    Client for hosted Hugging Face Inference Providers.
    Default model: Qwen/Qwen3-Embedding-0.6B (1024 dimensions, Apache 2.0 license).
    """

    DEFAULT_MODEL = 'Qwen/Qwen3-Embedding-0.6B'
    DEFAULT_DIMENSION = 1024

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_identifier: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        expected_dimension: Optional[int] = None,
    ):
        model = model_identifier or self.DEFAULT_MODEL
        dim = expected_dimension if expected_dimension is not None else (
            self.DEFAULT_DIMENSION if model == self.DEFAULT_MODEL else None
        )
        super().__init__(model_identifier=model, timeout=timeout, expected_dimension=dim)

        self.api_key = (api_key or '').strip()
        if not self.api_key:
            raise EmbeddingConfigurationError(
                "Hugging Face embedding provider requires an API key. "
                "Please configure EMBEDDING_API_KEY or HF_TOKEN in the environment."
            )

        if base_url and base_url.strip():
            self.endpoint = base_url.strip()
        else:
            self.endpoint = f"https://api-inference.huggingface.co/models/{self.model_identifier}"

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ManufacturingManualAssistant/1.0",
        }

    def _execute_request(self, payload: dict) -> requests.Response:
        try:
            response = requests.post(
                self.endpoint,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )
        except requests.exceptions.Timeout as e:
            raise EmbeddingTimeoutError(
                f"Hugging Face embedding request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise EmbeddingProviderError(
                f"Failed to connect to Hugging Face embedding endpoint: {e}"
            ) from e

        if response.status_code == 401 or response.status_code == 403:
            raise EmbeddingAuthenticationError(
                "Hugging Face authentication failed (HTTP 401/403). Check your EMBEDDING_API_KEY."
            )

        if response.status_code == 429:
            raise EmbeddingRateLimitError(
                "Hugging Face rate limit exceeded (HTTP 429). Retry after backoff."
            )

        if not response.ok:
            # Sanitize error output to prevent credential leaking
            error_body = response.text[:300]
            raise EmbeddingProviderError(
                f"Hugging Face API returned error (HTTP {response.status_code}): {error_body}"
            )

        return response

    def embed_text(self, text: str) -> List[float]:
        """Generates embedding for a single text chunk."""
        if not text or not text.strip():
            raise EmbeddingProviderError("Cannot embed empty text.")

        response = self._execute_request({"inputs": text})
        data = response.json()

        # Handle standard HF serverless response: either [float, ...] or [[float, ...]]
        if isinstance(data, list) and data and isinstance(data[0], list):
            embedding = data[0]
        elif isinstance(data, list) and data and isinstance(data[0], (int, float)):
            embedding = data
        elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            # OpenAI-compatible router format
            embedding = data["data"][0]["embedding"]
        else:
            raise EmbeddingProviderError(f"Unexpected Hugging Face response format: {type(data)}")

        return self.validate_embedding(embedding)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of text chunks."""
        if not texts:
            return []

        cleaned_texts = [t.strip() for t in texts if t and t.strip()]
        if not cleaned_texts:
            raise EmbeddingProviderError("All texts in batch are empty.")

        response = self._execute_request({"inputs": cleaned_texts})
        data = response.json()

        embeddings = []
        if isinstance(data, list) and data and isinstance(data[0], list):
            embeddings = data
        elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            # OpenAI-compatible format sorted by index
            sorted_items = sorted(data["data"], key=lambda x: x.get("index", 0))
            embeddings = [item["embedding"] for item in sorted_items]
        else:
            raise EmbeddingProviderError(f"Unexpected Hugging Face batch response format: {type(data)}")

        if len(embeddings) != len(cleaned_texts):
            raise EmbeddingProviderError(
                f"Batch size mismatch: sent {len(cleaned_texts)} texts, received {len(embeddings)} embeddings."
            )

        return [self.validate_embedding(emb) for emb in embeddings]

