"""
Factory for instantiating the configured embedding provider.
Strictly forbids silent fallback between providers to prevent embedding space collisions.
"""

from django.conf import settings
from typing import Optional

from .base import BaseEmbeddingProvider, EmbeddingConfigurationError
from .huggingface import HuggingFaceEmbeddingProvider
from .lm_studio import LMStudioEmbeddingProvider


def get_embedding_provider(
    provider_name: Optional[str] = None,
    model_identifier: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
) -> BaseEmbeddingProvider:
    """
    Returns an instance of the configured BaseEmbeddingProvider.
    If the requested provider is unsupported or invalid, raises EmbeddingConfigurationError.
    Never silently falls back to an alternative provider.
    """
    active_provider = (
        provider_name or getattr(settings, 'EMBEDDING_PROVIDER', 'huggingface')
    ).lower().strip()

    req_timeout = timeout or getattr(settings, 'EMBEDDING_REQUEST_TIMEOUT', 30)

    if active_provider == 'huggingface':
        key = api_key if api_key is not None else getattr(settings, 'EMBEDDING_API_KEY', '')
        model = model_identifier or getattr(settings, 'EMBEDDING_MODEL', HuggingFaceEmbeddingProvider.DEFAULT_MODEL)
        url = base_url if base_url is not None else getattr(settings, 'EMBEDDING_BASE_URL', '')

        return HuggingFaceEmbeddingProvider(
            api_key=key,
            model_identifier=model,
            base_url=url,
            timeout=req_timeout,
        )

    elif active_provider in ('lm_studio', 'lmstudio'):
        url = base_url or getattr(settings, 'LM_STUDIO_BASE_URL', LMStudioEmbeddingProvider.DEFAULT_BASE_URL)
        model = model_identifier or getattr(settings, 'LM_STUDIO_EMBEDDING_MODEL', LMStudioEmbeddingProvider.DEFAULT_MODEL)

        return LMStudioEmbeddingProvider(
            base_url=url,
            model_identifier=model,
            timeout=req_timeout,
        )

    else:
        raise EmbeddingConfigurationError(
            f"Unsupported embedding provider: '{active_provider}'. "
            f"Valid options are 'huggingface' or 'lm_studio'. "
            f"Silent fallback between providers is strictly prohibited."
        )

