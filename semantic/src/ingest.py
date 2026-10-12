# src/ingest.py

from __future__ import annotations

import argparse
from pathlib import Path

from .chunker import create_chunks
from .embeddings import generate_embeddings
from .pdf_processor import extract_pages
from .vector_store import (
    get_chroma_client,
    get_collection,
    upsert_chunks,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PDF_DIRECTORY = PROJECT_ROOT / "data" / "pdfs"

CHROMA_DIRECTORY = PROJECT_ROOT / "chroma"


def ingest_pdf(pdf_path: Path) -> None:
    """
    Complete PDF ingestion pipeline.
    """

    print(f"\nProcessing: {pdf_path.name}")

    # 1. Extract PDF pages.
    file_hash, pages = extract_pages(
        pdf_path=pdf_path,
        allowed_directory=PDF_DIRECTORY,
    )

    print(f"Pages containing text: {len(pages)}")

    # 2. Use the file hash as a stable document ID.
    document_id = file_hash[:24]

    # 3. Create chunks.
    chunks = create_chunks(
        pages=pages,
        document_id=document_id,
        file_name=pdf_path.name,
        chunk_size=500,
        overlap=75,
    )

    print(f"Chunks created: {len(chunks)}")

    if not chunks:
        raise ValueError(
            "No text chunks were created from this PDF."
        )

    # 4. Generate embeddings.
    texts = [
        chunk.text
        for chunk in chunks
    ]

    embeddings = generate_embeddings(texts)

    print(
        f"Embeddings generated: {len(embeddings)}"
    )

    # 5. Connect to Chroma.
    client = get_chroma_client(
        CHROMA_DIRECTORY
    )

    collection = get_collection(client)

    # 6. Store everything.
    upsert_chunks(
        collection=collection,
        chunks=chunks,
        embeddings=embeddings,
    )

    print(
        f"Stored {len(chunks)} chunks in Chroma."
    )

    print(
        f"Document ID: {document_id}"
    )


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description="Index a PDF into ChromaDB."
    )

    parser.add_argument(
        "pdf",
        type=str,
        help="PDF filename inside data/pdfs/",
    )

    return parser.parse_args()


def main() -> None:

    args = parse_args()

    pdf_name = Path(args.pdf).name

    # Only allow a filename, not an arbitrary path.
    if pdf_name != args.pdf:
        raise ValueError(
            "Only PDF filenames inside data/pdfs are allowed."
        )

    pdf_path = PDF_DIRECTORY / pdf_name

    ingest_pdf(pdf_path)


if __name__ == "__main__":
    main()