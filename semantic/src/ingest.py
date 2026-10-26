# semantic/src/ingest.py

from __future__ import annotations
import sys

import argparse
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .chunker import create_chunks
from .config import CHUNK_OVERLAP_WORDS, CHUNK_SIZE_WORDS, PDF_DIRECTORY
from .embeddings import generate_embeddings
from .pdf_processor import (
    PdfProcessingError,
    calculate_file_hash,
    extract_pages,
    read_pdf_file,
)
from .vector_store import (
    delete_document,
    get_default_collection,
    upsert_chunks,
)


# Only letters, numbers, "_" and "-" (max 64). The id is used inside
# chunk ids and database filters, so we keep it simple and safe.
DOCUMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    filename: str
    page_count: int
    chunk_count: int


def clean_filename(filename: str) -> str:
    """Keep only the file name. Remove any folders (C:\\x\\a.pdf -> a.pdf)."""

    name = PurePosixPath(filename.replace("\\", "/")).name.strip()

    if not name or len(name) > 255:
        raise ValueError("filename is empty or too long.")

    return name


def ingest_pdf_bytes(
    data: bytes,
    document_id: str,
    filename: str,
    collection=None,
) -> IngestResult:
    """
    The whole pipeline:
    PDF bytes -> pages -> chunks -> embeddings -> ChromaDB.
    """

    if not DOCUMENT_ID_PATTERN.match(document_id):
        raise ValueError(
            "document_id may contain only letters, numbers, "
            "'_' and '-' (max 64 characters)."
        )

    filename = clean_filename(filename)

    if collection is None:
        collection = get_default_collection()

    # 1. Read the PDF (raises PdfProcessingError if it is bad).
    pdf = extract_pages(data)

    # 2. Split into chunks.
    chunks = create_chunks(
        pages=pdf.pages,
        document_id=document_id,
        filename=filename,
        chunk_size=CHUNK_SIZE_WORDS,
        overlap=CHUNK_OVERLAP_WORDS,
    )

    if not chunks:
        raise PdfProcessingError(
            "NO_EXTRACTABLE_TEXT",
            "No text chunks could be created from this PDF.",
        )

    # 3. Make embeddings. This is the slow step, and it can fail,
    #    so we do it BEFORE touching the database.
    embeddings = generate_embeddings([chunk.text for chunk in chunks])

    # 4. Remove old chunks of this document (safe re-ingest), then save.
    delete_document(collection, document_id)
    upsert_chunks(collection, chunks, embeddings)

    return IngestResult(
        document_id=document_id,
        filename=filename,
        page_count=pdf.page_count,
        chunk_count=len(chunks),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index a PDF into ChromaDB.")
    parser.add_argument("pdf", type=str, help="PDF file name inside data/pdfs/")
    return parser.parse_args()


def main() -> None:
    sys.stdout.reconfigure(errors="replace")
    args = parse_args()

    pdf_name = Path(args.pdf).name

    # Only a file NAME is allowed, not a path like ..\\..\\secret.pdf
    if pdf_name != args.pdf:
        print("Error: give only a file name from data/pdfs, not a path.")
        raise SystemExit(1)

    try:
        data = read_pdf_file(PDF_DIRECTORY / pdf_name, PDF_DIRECTORY)

        # Same file contents -> same id. Re-running does not duplicate.
        document_id = calculate_file_hash(data)[:24]

        print(f"Processing {pdf_name} (the first run downloads the model)...")

        result = ingest_pdf_bytes(data, document_id, pdf_name)

    except PdfProcessingError as error:
        print(f"Error ({error.code}): {error.message}")
        raise SystemExit(1)

    print(f"Pages in PDF:     {result.page_count}")
    print(f"Chunks stored:    {result.chunk_count}")
    print(f"Document ID:      {result.document_id}")


if __name__ == "__main__":
    main()