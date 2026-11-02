"""
Hosted OpenAI-compatible LLM client for hosted models (e.g. Hugging Face router, Groq, OpenRouter).
"""

import requests
from typing import Optional
from .base import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
    LLMResult,
)


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    """
    LLM provider connecting to any standard OpenAI-compatible hosted API.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        model_identifier: str = "default-model",
        timeout: int = 60,
        temperature: float = 0.1,
    ):
        super().__init__(model_identifier=model_identifier, timeout=timeout, temperature=temperature)
        self.base_url = (base_url or '').rstrip('/')
        if not self.base_url:
            raise LLMConfigurationError("OpenAI-compatible LLM provider requires a non-empty base_url.")
        self.endpoint = f"{self.base_url}/chat/completions" if not self.base_url.endswith('/chat/completions') else self.base_url
        self.api_key = (api_key or '').strip()

    def generate_chat_completion(
        self,
        system_instruction: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> LLMResult:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ManufacturingManualAssistant/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_identifier,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
        except requests.exceptions.Timeout as e:
            raise LLMTimeoutError(f"Hosted LLM request timed out after {self.timeout}s: {e}") from e
        except requests.exceptions.RequestException as e:
            raise LLMProviderError(f"Hosted LLM request error: {e}") from e

        if response.status_code in (401, 403):
            raise LLMAuthenticationError("Hosted LLM API key authentication failed (HTTP 401/403).")

        if not response.ok:
            raise LLMProviderError(f"Hosted LLM returned HTTP {response.status_code}: {response.text[:300]}")

        data = response.json()
        try:
            msg = data["choices"][0]["message"]
            content = msg.get("content")
            if not content and msg.get("reasoning_content"):
                content = msg.get("reasoning_content")
            if content is None:
                content = ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMProviderError(f"Malformed response from hosted LLM: {data}") from e

        return LLMResult(raw_text=content, model_identifier=self.model_identifier)

