"""
Google Gemini API LLM Provider for Grounded Answer Generation.
Uses the official google-genai SDK with strict error handling,
temperature control, and canonical response normalization.
"""

import logging
from typing import Optional

from google import genai
from google.genai import errors
from google.genai import types

from .base import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMModelUnavailableError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMResponseMalformedError,
    LLMResult,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


class GeminiLLMProvider(BaseLLMProvider):
    """
    Google Gemini API provider executing grounded completion calls
    via the official google.genai Client.
    """

    DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_identifier: Optional[str] = None,
        timeout: int = 60,
        temperature: float = 0.1,
    ):
        model = (model_identifier or self.DEFAULT_MODEL).strip()
        super().__init__(model_identifier=model, timeout=timeout, temperature=temperature)

        self.api_key = (api_key or "").strip()
        if not self.api_key:
            raise LLMConfigurationError(
                "GEMINI_API_KEY is not configured in environment."
            )

    def _get_client(self) -> genai.Client:
        return genai.Client(api_key=self.api_key)

    @property
    def client(self) -> genai.Client:
        return self._get_client()

    def generate_chat_completion(
        self,
        system_instruction: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> LLMResult:
        """
        Executes chat completion with Google Gemini.
        Normalizes provider errors and returns standard LLMResult.
        """
        client = self._get_client()
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=self.temperature,
            max_output_tokens=max_tokens,
        )

        try:
            response = client.models.generate_content(
                model=self.model_identifier,
                contents=user_prompt,
                config=config,
            )

        except errors.APIError as exc:
            status_code = getattr(exc, "code", None)
            message = str(exc)

            # Bounded, non-freezing retry on transient 429 rate limit or 503 demand spike
            import time
            msg_lower = message.lower()
            is_rate_or_transient = (
                status_code in (429, 503)
                or "resource_exhausted" in msg_lower
                or "rate limit" in msg_lower
                or "unavailable" in msg_lower
            )
            is_hard_quota = "exceeded your current quota" in msg_lower
            if is_rate_or_transient and not is_hard_quota:
                for attempt, wait_sec in enumerate((1.0, 2.0), start=1):
                    logger.warning(
                        "Gemini transient/rate-limit error (status=%s, model=%s). Retry %d/2 in %.1fs.",
                        status_code, self.model_identifier, attempt, wait_sec,
                    )
                    time.sleep(wait_sec)
                    try:
                        response = client.models.generate_content(
                            model=self.model_identifier,
                            contents=user_prompt,
                            config=config,
                        )
                        return LLMResult(
                            raw_text=(response.text or "").strip(),
                            model_identifier=self.model_identifier,
                        )
                    except Exception as retry_err:
                        logger.warning(
                            "Gemini retry %d/2 failed (model=%s): %s",
                            attempt, self.model_identifier, type(retry_err).__name__,
                        )

            fallback_models = [
                m for m in [
                    "gemini-flash-lite-latest",
                    "gemini-flash-latest",
                    "gemini-3-flash-preview",
                    "gemini-3.1-flash-lite-preview",
                ]
                if m != self.model_identifier
            ]
            if (
                (status_code == 404 and ("not found" in message.lower() or "no longer available" in message.lower()))
                or status_code in (429, 503)
                or is_rate_or_transient
            ):
                for alt_model in fallback_models:
                    try:
                        time.sleep(0.5)
                        response = client.models.generate_content(
                            model=alt_model,
                            contents=user_prompt,
                            config=config,
                        )
                        raw_alt = (response.text or "").strip()
                        if raw_alt:
                            logger.info("Gemini fallback succeeded using model '%s'.", alt_model)
                            return LLMResult(
                                raw_text=raw_alt,
                                model_identifier=alt_model,
                            )
                    except Exception:
                        continue

                if status_code == 404:
                    raise LLMModelUnavailableError(
                        f"Requested Gemini model '{self.model_identifier}' is unavailable or not found: {message}"
                    ) from exc
                elif "quota" in message.lower():
                    raise LLMQuotaExhaustedError(
                        f"Google Gemini quota has been exhausted: {message}"
                    ) from exc
                elif status_code == 429 or "resource_exhausted" in message.lower() or "rate limit" in message.lower():
                    raise LLMRateLimitError(
                        f"Google Gemini rate limit exceeded: {message}"
                    ) from exc
                else:
                    raise LLMProviderError(
                        f"Google Gemini service temporarily unavailable ({status_code}): {message}"
                    ) from exc
            elif status_code in (401, 403) or "API_KEY_INVALID" in message or "PERMISSION_DENIED" in message or "not valid" in message.lower():
                raise LLMAuthenticationError(f"Google Gemini authentication failed: {message}") from exc
            elif "quota" in message.lower():
                raise LLMQuotaExhaustedError(f"Google Gemini quota has been exhausted: {message}") from exc
            elif status_code == 429 or "RESOURCE_EXHAUSTED" in message or "rate limit" in message.lower():
                raise LLMRateLimitError(f"Google Gemini rate limit exceeded: {message}") from exc
            elif status_code == 404 or "NOT_FOUND" in message or "not found" in message.lower():
                raise LLMModelUnavailableError(
                    f"Requested Gemini model '{self.model_identifier}' is unavailable or not found: {message}"
                ) from exc
            elif "DEADLINE_EXCEEDED" in message or "TIMEOUT" in message:
                raise LLMTimeoutError(f"Google Gemini request timed out: {message}") from exc
            else:
                raise LLMProviderError(f"Google Gemini API error ({status_code}): {message}") from exc

        except TimeoutError as exc:
            raise LLMTimeoutError(f"Google Gemini request timed out after {self.timeout}s: {exc}") from exc
        except (LLMProviderError, LLMAuthenticationError, LLMRateLimitError, LLMQuotaExhaustedError, LLMModelUnavailableError, LLMTimeoutError, LLMResponseMalformedError):
            raise
        except Exception as exc:
            raise LLMProviderError(f"Unexpected error communicating with Google Gemini API: {exc}") from exc

        if not response or not hasattr(response, "text"):
            raise LLMResponseMalformedError("Google Gemini returned an empty or unparseable response.")

        raw_text = getattr(response, "text", None)
        if raw_text is None:
            raise LLMResponseMalformedError("Google Gemini returned an empty or unparseable response.")

        raw_text = raw_text.strip()
        if not raw_text:
            try:
                candidates = getattr(response, "candidates", [])
                if candidates and candidates[0].content and candidates[0].content.parts:
                    raw_text = "".join(
                        part.text for part in candidates[0].content.parts if getattr(part, "text", None)
                    ).strip()
            except Exception:
                pass

        if not raw_text:
            raise LLMResponseMalformedError("Google Gemini returned an empty or unparseable response.")

        return LLMResult(
            raw_text=raw_text,
            model_identifier=self.model_identifier,
        )
