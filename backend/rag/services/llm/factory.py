"""
Factory for instantiating the configured LLM provider.
Defaults strictly to Google Gemini API.
Does NOT silently fallback to LM Studio / Qwen when Gemini fails.
"""

from typing import Optional
from django.conf import settings

from .base import BaseLLMProvider, LLMConfigurationError
from .gemini import GeminiLLMProvider
from .lm_studio import LMStudioLLMProvider
from .openai_client import OpenAICompatibleLLMProvider


def get_llm_provider(
    provider_name: Optional[str] = None,
    model_identifier: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    temperature: Optional[float] = None,
) -> BaseLLMProvider:
    """
    Returns an instance of BaseLLMProvider configured from Django settings or explicit arguments.
    Defaults to 'gemini'.
    """
    active_provider = (
        provider_name or getattr(settings, 'LLM_PROVIDER', 'gemini')
    ).lower().strip()

    req_timeout = timeout if timeout is not None else getattr(settings, 'LLM_TIMEOUT', 60)
    req_temp = temperature if temperature is not None else getattr(settings, 'LLM_TEMPERATURE', 0.1)

    if active_provider in ('gemini', 'google_gemini', 'google'):
        key = api_key if api_key is not None else getattr(settings, 'GEMINI_API_KEY', '')
        model = model_identifier or getattr(settings, 'GEMINI_MODEL', GeminiLLMProvider.DEFAULT_MODEL)

        return GeminiLLMProvider(
            api_key=key,
            model_identifier=model,
            timeout=req_timeout,
            temperature=req_temp,
        )

    elif active_provider in ('openai', 'openai_compatible', 'huggingface'):
        url = base_url or getattr(settings, 'LLM_BASE_URL', '')
        model = model_identifier or getattr(settings, 'LLM_MODEL', 'default-model')
        key = api_key if api_key is not None else getattr(settings, 'LLM_API_KEY', '')

        if not url:
            raise LLMConfigurationError(
                f"LLM provider '{active_provider}' requires LLM_BASE_URL to be configured."
            )

        return OpenAICompatibleLLMProvider(
            base_url=url,
            api_key=key,
            model_identifier=model,
            timeout=req_timeout,
            temperature=req_temp,
        )

    elif active_provider in ('lm_studio', 'lmstudio'):
        url = base_url or getattr(settings, 'LLM_BASE_URL', LMStudioLLMProvider.DEFAULT_BASE_URL)
        model = model_identifier or getattr(settings, 'LLM_MODEL', LMStudioLLMProvider.DEFAULT_MODEL)

        return LMStudioLLMProvider(
            base_url=url,
            model_identifier=model,
            timeout=req_timeout,
            temperature=req_temp,
        )

    else:
        raise LLMConfigurationError(
            f"Unsupported LLM provider: '{active_provider}'. "
            f"Configured provider must be 'gemini', 'openai_compatible', or 'lm_studio'."
        )
