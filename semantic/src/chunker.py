# src/chunker.py

from __future__ import annotations

from dataclasses import dataclass

from .pdf_processor import PageText


DEFAULT_CHUNK_SIZE = 500
DEFAULT_OVERLAP = 75

MIN_CHUNK_SIZE = 50
MAX_CHUNK_SIZE = 2_000


@dataclass(frozen=True)
class TextChunk:
    """
    Represents one searchable chunk.
    """

    chunk_id: str
    document_id: str
    file_name: str
    page_number: int
    chunk_number: int
    text: str


def validate_chunk_settings(
    chunk_size: int,
    overlap: int,
) -> None:

    if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
        raise ValueError(
            f"chunk_size must be between "
            f"{MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE}."
        )

    if overlap < 0:
        raise ValueError("overlap cannot be negative.")

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size."
        )


def split_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """
    Split text into overlapping word-based chunks.
    """

    validate_chunk_settings(chunk_size, overlap)

    words = text.split()

    if not words:
        return []

    chunks: list[str] = []

    start = 0

    while start < len(words):

        end = min(
            start + chunk_size,
            len(words),
        )

        chunk = " ".join(words[start:end]).strip()

        if chunk:
            chunks.append(chunk)

        if end == len(words):
            break

        start = end - overlap

    return chunks


def create_chunks(
    pages: list[PageText],
    document_id: str,
    file_name: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[TextChunk]:
    """
    Convert page text into searchable chunks while preserving
    document/page/chunk information.
    """

    chunks: list[TextChunk] = []

    global_chunk_number = 0

    for page in pages:

        page_chunks = split_text(
            page.text,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for page_chunk_number, text in enumerate(
            page_chunks,
            start=1,
        ):

            global_chunk_number += 1

            chunk_id = (
                f"{document_id}"
                f"_p{page.page_number}"
                f"_c{page_chunk_number}"
            )

            chunks.append(
                TextChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    file_name=file_name,
                    page_number=page.page_number,
                    chunk_number=global_chunk_number,
                    text=text,
                )
            )

    return chunks