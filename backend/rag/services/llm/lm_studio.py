"""
LM Studio local LLM client using OpenAI-compatible /v1/chat/completions endpoint.
"""

import requests
from typing import Optional
from .base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMResult,
)


class LMStudioLLMProvider(BaseLLMProvider):
    """
    LLM provider connecting to a local LM Studio server.
    Default model: qwen/qwen3-8b.
    """

    DEFAULT_BASE_URL = 'http://127.0.0.1:1234/v1'
    DEFAULT_MODEL = 'qwen/qwen3-8b'

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_identifier: Optional[str] = None,
        timeout: int = 60,
        temperature: float = 0.1,
    ):
        model = (model_identifier or self.DEFAULT_MODEL).strip()
        super().__init__(model_identifier=model, timeout=timeout, temperature=temperature)
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip('/')
        self.endpoint = f"{self.base_url}/chat/completions"

    def generate_chat_completion(
        self,
        system_instruction: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> LLMResult:
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
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout
            )
        except requests.exceptions.Timeout as e:
            raise LLMTimeoutError(
                f"LM Studio chat completion timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise LLMProviderError(
                f"Could not connect to LM Studio at {self.endpoint}. "
                f"Ensure LM Studio local server is active: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMProviderError(f"LM Studio HTTP request error: {e}") from e

        if not response.ok:
            raise LLMProviderError(
                f"LM Studio API returned HTTP {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        try:
            msg = data["choices"][0]["message"]
            content = msg.get("content")
            if not content and msg.get("reasoning_content"):
                content = msg.get("reasoning_content")
            if content is None:
                content = ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMProviderError(f"Malformed chat completion response from LM Studio: {data}") from e

        return LLMResult(raw_text=content, model_identifier=self.model_identifier)

