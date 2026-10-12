# src/search.py

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .embeddings import generate_query_embedding
from .vector_store import (
    get_chroma_client,
    get_collection,
    search_chunks,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHROMA_DIRECTORY = PROJECT_ROOT / "chroma"


def run_search(
    query: str,
    top_k: int = 5,
    document_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Search the Chroma collection and return clean results.
    """

    query_embedding = generate_query_embedding(
        query
    )

    client = get_chroma_client(
        CHROMA_DIRECTORY
    )

    collection = get_collection(client)

    where = None

    if document_id:
        document_id = document_id.strip()

        if not document_id:
            raise ValueError(
                "document_id cannot be empty."
            )

        where = {
            "document_id": document_id
        }

    raw_results = search_chunks(
        collection=collection,
        query_embedding=query_embedding,
        top_k=top_k,
        where=where,
    )

    return format_results(raw_results)


def format_results(
    results: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert Chroma's nested response into
    easy-to-use result objects.
    """

    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    documents = documents[0]
    metadatas = metadatas[0]
    distances = distances[0]

    formatted: list[dict[str, Any]] = []

    for index, text in enumerate(documents):

        metadata = metadatas[index]

        formatted.append(
            {
                "file_name": metadata["file_name"],
                "page_number": metadata["page_number"],
                "chunk_number": metadata["chunk_number"],
                "distance": distances[index],
                "text": text,
            }
        )

    return formatted


def print_results(
    results: list[dict[str, Any]],
) -> None:

    if not results:
        print("\nNo relevant results found.")
        return

    print("\n" + "=" * 60)
    print("SEARCH RESULTS")
    print("=" * 60)

    for index, result in enumerate(
        results,
        start=1,
    ):

        print(f"\nResult {index}")
        print("-" * 60)

        print(
            f"PDF: {result['file_name']}"
        )

        print(
            f"Page: {result['page_number']}"
        )

        print(
            f"Chunk: {result['chunk_number']}"
        )

        print(
            f"Distance: {result['distance']:.4f}"
        )

        print("\nText:")
        print(result["text"])


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description="Semantic search over indexed PDFs."
    )

    parser.add_argument(
        "query",
        type=str,
        help="Question to search for.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results.",
    )

    parser.add_argument(
        "--document-id",
        type=str,
        default=None,
        help="Optional document ID filter.",
    )

    return parser.parse_args()


def main() -> None:

    args = parse_args()

    results = run_search(
        query=args.query,
        top_k=args.top_k,
        document_id=args.document_id,
    )

    print_results(results)


if __name__ == "__main__":
    main()