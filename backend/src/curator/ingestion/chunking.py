"""Sentence-aware chunking with character offsets.

Offsets are kept so that evidence quoted by the LLM can be highlighted in the
original profile. Chunks never split a sentence and overlap by one sentence,
which keeps enumerations ("M&A, reestruturação e captação") intact.
"""

import re

from curator.domain.models import Chunk

_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÀ-Ý0-9(])")


def split_sentences(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _SENTENCE_END.finditer(text):
        spans.append((start, match.start()))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def chunk_text(
    candidate_id: str, text: str, max_chars: int = 220, overlap_sentences: int = 1
) -> list[Chunk]:
    sentences = split_sentences(text)
    chunks: list[Chunk] = []
    i = 0
    while i < len(sentences):
        j = i
        while j + 1 < len(sentences) and sentences[j + 1][1] - sentences[i][0] <= max_chars:
            j += 1
        start, end = sentences[i][0], sentences[j][1]
        chunks.append(
            Chunk(
                chunk_id=f"{candidate_id}:{len(chunks)}",
                candidate_id=candidate_id,
                text=text[start:end],
                start=start,
                end=end,
            )
        )
        if j + 1 >= len(sentences):
            break
        i = max(j + 1 - overlap_sentences, i + 1)
    return chunks
