# semantic/src/search.py

from __future__ import annotations

import argparse
from typing import Any

from .config import MAX_DISTANCE, TOP_K_DEFAULT
from .embeddings import generate_query_embedding
from .vector_store import MAX_TOP_K, get_default_collection, search_chunks


MATCH_MESSAGE = (
    "Showing the most relevant source excerpts. "
    "These are passages from your documents, not a generated answer."
)
NO_MATCH_MESSAGE = (
    "No sufficiently relevant passages were found in the uploaded documents."
)
EMPTY_INDEX_MESSAGE = "No documents have been indexed yet."


def _response(
    query: str,
    results: list[dict[str, Any]],
    message: str,
) -> dict[str, Any]:
    return {
        "query": query,
        "no_match": len(results) == 0,
        "message": message,
        "results": results,
    }


def format_results(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn Chroma's nested lists into a simple list of result dicts."""

    ids = (raw.get("ids") or [[]])[0]
    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    results: list[dict[str, Any]] = []

    for chunk_id, text, metadata, distance in zip(
        ids, documents, metadatas, distances
    ):
        results.append(
            {
                "chunk_id": chunk_id,
                "document_id": metadata["document_id"],
                "filename": metadata["filename"],
                "page_number": metadata["page_number"],
                "text": text,
                "distance": round(float(distance), 4),
            }
        )

    return results


def run_search(
    query: str,
    top_k: int | None = None,
    document_id: str | None = None,
    max_distance: float | None = None,
    collection=None,
) -> dict[str, Any]:
    """Search the indexed PDFs. Returns the response format of our API."""

    query = (query or "").strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    top_k = TOP_K_DEFAULT if top_k is None else top_k
    max_distance = MAX_DISTANCE if max_distance is None else max_distance

    if not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}.")

    if collection is None:
        collection = get_default_collection()

    if collection.count() == 0:
        return _response(query, [], EMPTY_INDEX_MESSAGE)

    where = None

    if document_id is not None:
        document_id = document_id.strip()

        if not document_id:
            raise ValueError("document_id cannot be empty.")

        where = {"document_id": document_id}

    query_embedding = generate_query_embedding(query)

    raw = search_chunks(collection, query_embedding, top_k, where)

    # Keep only chunks that are close enough.
    results = [
        result
        for result in format_results(raw)
        if result["distance"] <= max_distance
    ]

    if not results:
        return _response(query, [], NO_MATCH_MESSAGE)

    return _response(query, results, MATCH_MESSAGE)


def print_response(response: dict[str, Any]) -> None:
    print("\n" + response["message"])

    for number, result in enumerate(response["results"], start=1):
        print("\n" + "-" * 60)
        print(f"Result {number}")
        print(f"PDF:      {result['filename']}")
        print(f"Page:     {result['page_number']}")
        print(f"Distance: {result['distance']:.4f}  (lower = closer)")
        print(f"Text:     {result['text']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search indexed PDFs.")
    parser.add_argument("query", type=str, help="Your question.")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--document-id", type=str, default=None)
    parser.add_argument(
        "--max-distance",
        type=float,
        default=None,
        help="Use 2 to see every result with its real distance (for tuning).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    response = run_search(
        query=args.query,
        top_k=args.top_k,
        document_id=args.document_id,
        max_distance=args.max_distance,
    )

    print_response(response)


if __name__ == "__main__":
    main()