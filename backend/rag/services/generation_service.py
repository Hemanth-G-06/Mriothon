"""
Grounded Answer Generation & Citation Validation Service.
Enforces strict manufacturing manual grounding, precise citation validation against Neon records,
and exact canonical abstention when available context is insufficient.
Integrates with configurable LLM providers (default: Google Gemini API).
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMResult,
)
from .llm.factory import get_llm_provider
from .retrieval_service import RetrievedChunkContext

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are a manufacturing manual assistant. Answer the user's question using ONLY the supplied manual passages.

Rules:
1. Answer only using the supplied manual passages.
2. Do not use general model knowledge to fill missing information.
3. Do not infer technical specifications that are absent from the passages.
4. Do not invent procedures, torque values, measurements, part numbers, or safety instructions.
5. Do not use information from another machine's manual.
6. Explicitly abstain when the passages do not contain enough information to support an answer.
7. If only part of the question is supported, answer only that supported part and clearly identify what cannot be established.
8. Cite the source IDs supporting your answer.
9. Never fabricate document names, page numbers, or citations."""

EXACT_ABSTENTION_MESSAGE = "The available manual passages do not contain enough information to answer this question."


@dataclass
class VerifiedCitation:
    """
    Validated citation pointing strictly to a verified document and page in Neon PostgreSQL.
    """
    document_id: str
    document_title: str
    page_number: int
    source_id: str

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "page_number": self.page_number,
            "source_id": self.source_id,
        }


@dataclass
class GroundedAnswer:
    """
    End-to-end grounded answer returned to the API and client.
    """
    answer: str
    citations: List[dict]
    abstained: bool


class GroundedAnswerGenerationService:
    """
    Assembles grounded LLM prompts, generates answers via configured API provider,
    validates citations, and enforces strict factual abstention.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm_provider = llm_provider

    def _get_provider(self) -> BaseLLMProvider:
        if self.llm_provider is None:
            self.llm_provider = get_llm_provider()
        return self.llm_provider

    def generate_answer(
        self,
        machine_name: str,
        machine_code: str,
        question: str,
        retrieved_chunks: List[RetrievedChunkContext],
    ) -> GroundedAnswer:
        """
        Generates an answer strictly grounded in the retrieved passages.
        If context is empty or insufficient, returns canonical abstention.
        """
        # If no chunks were retrieved from ChromaDB/Neon for this machine
        if not retrieved_chunks:
            return GroundedAnswer(
                answer=EXACT_ABSTENTION_MESSAGE,
                citations=[],
                abstained=True,
            )

        # Index available source IDs for strict citation validation
        chunk_by_source_id: Dict[str, RetrievedChunkContext] = {
            chunk.source_id: chunk for chunk in retrieved_chunks
        }

        # Build formatted prompt passages
        passages_text_blocks = []
        for chunk in retrieved_chunks:
            passages_text_blocks.append(
                f"[SOURCE: {chunk.source_id}]\n"
                f"Document: {chunk.document_title} (Page {chunk.page_number})\n"
                f"Content:\n{chunk.chunk_text.strip()}\n"
            )

        passages_payload = "\n----------------------------------------\n".join(passages_text_blocks)

        user_prompt = (
            f"MACHINE: {machine_name} (Code: {machine_code})\n\n"
            f"--- VERIFIED MANUAL PASSAGES ---\n"
            f"{passages_payload}\n"
            f"--------------------------------\n\n"
            f"QUESTION: {question}\n\n"
            f"RESPONSE INSTRUCTIONS:\n"
            f"- Answer the question using ONLY the verified manual passages above.\n"
            f"- If the passages do not contain enough information, respond exactly with:\n"
            f"  {EXACT_ABSTENTION_MESSAGE}\n"
            f"- Format your response as:\n"
            f"  ANSWER: <your answer>\n"
            f"  SOURCES: [SOURCE_ID_1, SOURCE_ID_2]\n"
            f"- If you abstain, return SOURCES: []"
        )

        provider = self._get_provider()
        try:
            llm_response = provider.generate_chat_completion(
                system_instruction=SYSTEM_INSTRUCTION,
                user_prompt=user_prompt,
                max_tokens=600,
            )
        except LLMProviderError:
            # Re-raise typed provider error to be handled by caller/view
            raise
        except Exception as e:
            logger.error("Unexpected error in LLM provider completion: %s", type(e).__name__)
            raise LLMProviderError(f"LLM generation failed: {type(e).__name__}") from e

        raw_output = (llm_response.raw_text or '').strip()

        # Parse ANSWER and SOURCES
        parsed_answer, raw_sources = self._parse_llm_output(raw_output)

        # Check for abstention
        is_abstention = (
            EXACT_ABSTENTION_MESSAGE.lower() in parsed_answer.lower()
            or "not contain enough information" in parsed_answer.lower()
            or "cannot be answered" in parsed_answer.lower()
        )

        if is_abstention:
            return GroundedAnswer(
                answer=EXACT_ABSTENTION_MESSAGE,
                citations=[],
                abstained=True,
            )

        # Validate citations against verified Neon records
        verified_citations = self._validate_citations(
            raw_sources=raw_sources,
            answer_text=parsed_answer,
            available_sources=chunk_by_source_id,
        )

        # Strict citation integrity: do not attach arbitrary unverified fallback citations.
        # Citations are only attached if they explicitly map to verified source passages.

        return GroundedAnswer(
            answer=parsed_answer,
            citations=[c.to_dict() for c in verified_citations],
            abstained=False,
        )

    def _parse_llm_output(self, raw_text: str) -> tuple[str, List[str]]:
        """
        Extracts clean answer text and referenced source IDs from the LLM output.
        """
        # Strip any reasoning or think tags
        clean_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
        if not clean_text:
            clean_text = raw_text

        answer = clean_text
        sources: List[str] = []

        # Check for ANSWER: prefix
        answer_match = re.search(r'ANSWER:\s*(.*?)(?=\nSOURCES:|$)', clean_text, re.DOTALL | re.IGNORECASE)
        if answer_match:
            answer = answer_match.group(1).strip()
        else:
            # If no ANSWER: prefix, but SOURCES: exists, strip SOURCES: from answer
            sources_match = re.search(r'SOURCES:\s*\[?(.*?)\]?$', clean_text, re.DOTALL | re.IGNORECASE)
            if sources_match:
                answer = clean_text[:sources_match.start()].strip()

        # Check for SOURCES: line
        sources_match = re.search(r'SOURCES:\s*\[?(.*?)\]?$', clean_text, re.DOTALL | re.IGNORECASE)
        if sources_match:
            source_tokens = re.findall(r'DOC-[A-Z0-9]+-P\d+-C\d+', sources_match.group(1))
            sources.extend(source_tokens)

        # Secondary: find any DOC-XXXXXX-PX-CX pattern mentioned in the text
        if not sources:
            sources.extend(re.findall(r'DOC-[A-Z0-9]+-P\d+-C\d+', clean_text))

        return answer, sources

    def _validate_citations(
        self,
        raw_sources: List[str],
        answer_text: str,
        available_sources: Dict[str, RetrievedChunkContext],
    ) -> List[VerifiedCitation]:
        """
        Validates every referenced source against actual retrieved chunks.
        Discards fabricated / unretrieved source IDs. Deduplicates citations.
        """
        seen_keys = set()
        validated: List[VerifiedCitation] = []

        for src_id in raw_sources:
            if src_id in available_sources:
                chunk = available_sources[src_id]
                key = (chunk.document_id, chunk.page_number)
                if key not in seen_keys:
                    seen_keys.add(key)
                    validated.append(
                        VerifiedCitation(
                            document_id=chunk.document_id,
                            document_title=chunk.document_title,
                            page_number=chunk.page_number,
                            source_id=chunk.source_id,
                        )
                    )

        return validated
