"""
Base class and exceptions for the LLM Provider architecture.
Supports hosted API providers (Google Gemini API, OpenAI-compatible APIs)
and optional local providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


class LLMProviderError(Exception):
    """Base exception for all LLM provider errors."""
    pass


class LLMConfigurationError(LLMProviderError):
    """Raised when the LLM provider is misconfigured or missing endpoint/credentials."""
    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM inference call times out."""
    pass


class LLMAuthenticationError(LLMProviderError):
    """Raised when an LLM API call fails authentication (401, 403, invalid key)."""
    pass


class LLMRateLimitError(LLMProviderError):
    """Raised when provider rate limits are exceeded (429 / resource exhausted)."""
    pass


class LLMQuotaExhaustedError(LLMRateLimitError):
    """Raised when provider quota is completely exhausted."""
    pass


class LLMModelUnavailableError(LLMProviderError):
    """Raised when the requested model identifier is unavailable or not found (404)."""
    pass


class LLMResponseMalformedError(LLMProviderError):
    """Raised when the provider returns an unparseable or empty response."""
    pass


@dataclass
class LLMResult:
    """
    Normalized response returned by an LLM provider.
    """
    raw_text: str
    model_identifier: str

    @property
    def model_name(self) -> str:
        return self.model_identifier


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM answer generation.
    """

    def __init__(
        self,
        model_identifier: str,
        timeout: int = 60,
        temperature: float = 0.1,
    ):
        self.model_identifier = model_identifier.strip()
        self.timeout = timeout
        self.temperature = temperature

    def get_model_identifier(self) -> str:
        return self.model_identifier

    @abstractmethod
    def generate_chat_completion(
        self,
        system_instruction: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> LLMResult:
        """
        Executes chat completion with the given system instruction and user prompt.
        Normalizes provider-specific formats into a standard LLMResult.
        """
        pass
