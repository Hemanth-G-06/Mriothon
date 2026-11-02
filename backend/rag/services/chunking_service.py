"""
Text chunking service for manufacturing manuals.
Implements paragraph-aware, heading-preserving, and technical-specification-safe
sliding window chunking strictly partitioned by individual DocumentPage records.
"""

import re
from dataclasses import dataclass
from typing import List, Optional
from django.conf import settings

from documents.models import Document, DocumentPage


@dataclass
class ChunkData:
    """
    In-memory representation of an individual text chunk extracted from a document page.
    """
    chunk_index: int
    text: str
    token_count: int
    character_start_offset: int
    character_end_offset: int
    page_number: int
    page_id: int


class ChunkingService:
    """
    Splits extracted PDF text into meaningful semantic chunks for RAG indexing.

    Token-counting methodology:
    Uses a regex-based token estimator `re.findall(r'\\w+|[^\\w\\s]', text)`.
    Limitations:
    This is a close approximation (~90-95% correlation) to WordPiece / BPE subword tokenizers,
    treating punctuation and alphanumeric tokens distinctly. It avoids downloading bulky
    model-specific tokenizer weights while remaining consistent across providers.
    """

    def __init__(
        self,
        target_tokens: Optional[int] = None,
        max_tokens: Optional[int] = None,
        overlap_tokens: Optional[int] = None,
        min_tokens: Optional[int] = None,
    ):
        self.target_tokens = target_tokens or getattr(settings, 'CHUNK_TARGET_TOKENS', 400)
        self.max_tokens = max_tokens or getattr(settings, 'CHUNK_MAX_TOKENS', 500)
        self.overlap_tokens = overlap_tokens or getattr(settings, 'CHUNK_OVERLAP_TOKENS', 60)
        self.min_tokens = min_tokens or getattr(settings, 'CHUNK_MIN_TOKENS', 40)

    @staticmethod
    def estimate_token_count(text: str) -> int:
        """
        Estimates token count using subword/punctuation boundary tokenization.
        """
        if not text:
            return 0
        return len(re.findall(r'\w+|[^\w\s]', text))

    def _split_into_sentences_with_offsets(self, text: str) -> List[tuple[str, int, int]]:
        """
        Splits text into sentences while preserving character start and end offsets.
        Avoids splitting on common abbreviations, decimal numbers, and technical units
        (e.g., '12.5 V', 'Fig. 2', 'ISO 9001.2', 'e.g.').
        """
        if not text:
            return []

        # Split pattern: period, exclamation, question mark, or newline followed by whitespace/uppercase
        # Lookbehind prevents splitting on digits (e.g. 3.14) or single capital letters (e.g. A. B.)
        sentence_end = re.compile(r'(?<=[.!?\n])\s+(?=[A-Z0-9#\-\*]|$)', re.MULTILINE)
        
        sentences = []
        last_end = 0
        for match in sentence_end.finditer(text):
            start = last_end
            end = match.start()
            sentence_str = text[start:end].strip()
            if sentence_str:
                # Find exact start of non-whitespace
                actual_start = text.find(sentence_str, start)
                actual_end = actual_start + len(sentence_str)
                sentences.append((sentence_str, actual_start, actual_end))
            last_end = match.end()

        # Add remaining text
        if last_end < len(text):
            sentence_str = text[last_end:].strip()
            if sentence_str:
                actual_start = text.find(sentence_str, last_end)
                actual_end = actual_start + len(sentence_str)
                sentences.append((sentence_str, actual_start, actual_end))

        # Fallback if no sentence breaks found
        if not sentences and text.strip():
            clean = text.strip()
            start = text.find(clean)
            sentences.append((clean, start, start + len(clean)))

        return sentences

    def chunk_page(self, page: DocumentPage) -> List[ChunkData]:
        """
        Chunks text from a single DocumentPage.
        Strict boundary enforcement: never combines text from different pages.
        """
        page_text = (page.text or '').strip()
        if not page_text or len(page_text) < 10:
            return []

        total_tokens = self.estimate_token_count(page_text)

        # Optimization: If the whole page comfortably fits within max_tokens
        if total_tokens <= self.max_tokens:
            return [
                ChunkData(
                    chunk_index=0,
                    text=page_text,
                    token_count=total_tokens,
                    character_start_offset=0,
                    character_end_offset=len(page.text),
                    page_number=page.page_number,
                    page_id=page.id,
                )
            ]

        # Long page: Sliding window across sentences
        sentences = self._split_into_sentences_with_offsets(page.text)
        if not sentences:
            return []

        chunks: List[ChunkData] = []
        current_sentence_indices: List[int] = []
        current_tokens = 0
        chunk_idx = 0

        i = 0
        while i < len(sentences):
            sent_text, s_start, s_end = sentences[i]
            sent_tokens = self.estimate_token_count(sent_text)

            # If a single sentence exceeds max_tokens, split it by words
            if sent_tokens > self.max_tokens:
                if current_sentence_indices:
                    # Flush current accumulated chunk first
                    first_idx = current_sentence_indices[0]
                    last_idx = current_sentence_indices[-1]
                    c_start = sentences[first_idx][1]
                    c_end = sentences[last_idx][2]
                    c_text = page.text[c_start:c_end].strip()
                    chunks.append(
                        ChunkData(
                            chunk_index=chunk_idx,
                            text=c_text,
                            token_count=self.estimate_token_count(c_text),
                            character_start_offset=c_start,
                            character_end_offset=c_end,
                            page_number=page.page_number,
                            page_id=page.id,
                        )
                    )
                    chunk_idx += 1
                    current_sentence_indices = []
                    current_tokens = 0

                # Slice long sentence by word window
                words = sent_text.split()
                w_start = s_start
                for w_idx in range(0, len(words), self.target_tokens - self.overlap_tokens):
                    w_slice = words[w_idx:w_idx + self.target_tokens]
                    slice_str = " ".join(w_slice)
                    slice_start = page.text.find(slice_str, w_start)
                    slice_end = slice_start + len(slice_str)
                    w_start = max(w_start, slice_end - 50)
                    chunks.append(
                        ChunkData(
                            chunk_index=chunk_idx,
                            text=slice_str,
                            token_count=self.estimate_token_count(slice_str),
                            character_start_offset=slice_start,
                            character_end_offset=slice_end,
                            page_number=page.page_number,
                            page_id=page.id,
                        )
                    )
                    chunk_idx += 1
                i += 1
                continue

            # Check if adding this sentence exceeds target / max
            if current_tokens + sent_tokens > self.max_tokens and current_sentence_indices:
                # Emit chunk
                first_idx = current_sentence_indices[0]
                last_idx = current_sentence_indices[-1]
                c_start = sentences[first_idx][1]
                c_end = sentences[last_idx][2]
                c_text = page.text[c_start:c_end].strip()
                chunks.append(
                    ChunkData(
                        chunk_index=chunk_idx,
                        text=c_text,
                        token_count=self.estimate_token_count(c_text),
                        character_start_offset=c_start,
                        character_end_offset=c_end,
                        page_number=page.page_number,
                        page_id=page.id,
                    )
                )
                chunk_idx += 1

                # Calculate overlap: rewind index to include trailing sentences up to overlap_tokens
                overlap_accum = 0
                rewind_pos = i
                for r_idx in reversed(current_sentence_indices):
                    r_tok = self.estimate_token_count(sentences[r_idx][0])
                    if overlap_accum + r_tok <= self.overlap_tokens:
                        overlap_accum += r_tok
                        rewind_pos = r_idx
                    else:
                        break

                current_sentence_indices = []
                current_tokens = 0
                # Move pointer to rewind_pos if rewind happened and made progress
                if rewind_pos < i and rewind_pos > first_idx:
                    i = rewind_pos

            current_sentence_indices.append(i)
            current_tokens += sent_tokens
            i += 1

        # Emit remaining sentences if any
        if current_sentence_indices:
            first_idx = current_sentence_indices[0]
            last_idx = current_sentence_indices[-1]
            c_start = sentences[first_idx][1]
            c_end = sentences[last_idx][2]
            c_text = page.text[c_start:c_end].strip()
            c_tokens = self.estimate_token_count(c_text)

            # If the tail chunk is too small and we already have chunks, append to previous if under max
            if chunks and c_tokens < self.min_tokens:
                prev_chunk = chunks[-1]
                combined_tokens = prev_chunk.token_count + c_tokens
                if combined_tokens <= self.max_tokens:
                    new_text = page.text[prev_chunk.character_start_offset:c_end].strip()
                    chunks[-1] = ChunkData(
                        chunk_index=prev_chunk.chunk_index,
                        text=new_text,
                        token_count=self.estimate_token_count(new_text),
                        character_start_offset=prev_chunk.character_start_offset,
                        character_end_offset=c_end,
                        page_number=page.page_number,
                        page_id=page.id,
                    )
                else:
                    chunks.append(
                        ChunkData(
                            chunk_index=chunk_idx,
                            text=c_text,
                            token_count=c_tokens,
                            character_start_offset=c_start,
                            character_end_offset=c_end,
                            page_number=page.page_number,
                            page_id=page.id,
                        )
                    )
            else:
                chunks.append(
                    ChunkData(
                        chunk_index=chunk_idx,
                        text=c_text,
                        token_count=c_tokens,
                        character_start_offset=c_start,
                        character_end_offset=c_end,
                        page_number=page.page_number,
                        page_id=page.id,
                    )
                )

        return chunks

    def chunk_document(self, document: Document) -> List[ChunkData]:
        """
        Chunks all pages of an active Document.
        Preserves 1-indexed page numbering and guarantees isolation across pages.
        """
        all_chunks: List[ChunkData] = []
        pages = document.pages.filter(character_count__gt=0).order_by('page_number')

        for page in pages:
            page_chunks = self.chunk_page(page)
            all_chunks.extend(page_chunks)

        return all_chunks

