# semantic/src/chunker.py

from __future__ import annotations

from dataclasses import dataclass

from .config import CHUNK_OVERLAP_WORDS, CHUNK_SIZE_WORDS
from .pdf_processor import PageText


# Sanity limits (in words).
# Warning: all-MiniLM-L6-v2 reads only ~256 tokens (about 190 words).
# Chunks much larger than that get silently cut off by the model.
MIN_CHUNK_SIZE = 50
MAX_CHUNK_SIZE = 2_000


@dataclass(frozen=True)
class TextChunk:
    """One searchable piece of a document."""

    chunk_id: str  # "<document_id>_p<page>_c<index>", e.g. "ab12_p4_c0"
    document_id: str
    filename: str
    page_number: int  # starts at 1
    chunk_index: int  # position within its page, starts at 0
    text: str


def validate_chunk_settings(chunk_size: int, overlap: int) -> None:
    if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
        raise ValueError(
            f"chunk_size must be between {MIN_CHUNK_SIZE} "
            f"and {MAX_CHUNK_SIZE}."
        )

    if overlap < 0:
        raise ValueError("overlap cannot be negative.")

    # If overlap >= chunk_size the window would never move forward
    # and the loop below would run forever.
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """Split text into overlapping chunks of `chunk_size` words."""

    validate_chunk_settings(chunk_size, overlap)

    words = text.split()  # splits on any whitespace, drops empties

    if not words:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))

        chunk = " ".join(words[start:end]).strip()

        if chunk:
            chunks.append(chunk)

        if end == len(words):
            break

        # Step back by `overlap` words so neighbors share context.
        start = end - overlap

    return chunks


def create_chunks(
    pages: list[PageText],
    document_id: str,
    filename: str,
    chunk_size: int = CHUNK_SIZE_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[TextChunk]:
    """Turn pages into chunks, keeping document and page identity."""

    chunks: list[TextChunk] = []

    for page in pages:
        page_chunks = split_text(
            page.text, chunk_size=chunk_size, overlap=overlap
        )

        for chunk_index, text in enumerate(page_chunks):
            chunks.append(
                TextChunk(
                    chunk_id=(
                        f"{document_id}"
                        f"_p{page.page_number}"
                        f"_c{chunk_index}"
                    ),
                    document_id=document_id,
                    filename=filename,
                    page_number=page.page_number,
                    chunk_index=chunk_index,
                    text=text,
                )
            )

    return chunks