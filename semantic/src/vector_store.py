# semantic/src/vector_store.py

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from .chunker import TextChunk
from .config import CHROMA_DIRECTORY, COLLECTION_NAME


MAX_TOP_K = 20


def get_chroma_client(persist_directory: Path):
    """Open (or create) a ChromaDB database stored in a folder on disk."""

    persist_directory = persist_directory.resolve()
    persist_directory.mkdir(parents=True, exist_ok=True)

    return chromadb.PersistentClient(
        path=str(persist_directory),
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection(client, name: str = COLLECTION_NAME):
    """
    Get the collection, or create it the first time.

    A collection is like a table. We tell Chroma to use COSINE distance.
    This setting is fixed when the collection is created.
    """

    return client.get_or_create_collection(
        name=name,
        configuration={"hnsw": {"space": "cosine"}},
    )


@lru_cache(maxsize=1)
def get_default_collection():
    """The real collection used by the app (opened once, then reused)."""

    client = get_chroma_client(CHROMA_DIRECTORY)
    return get_collection(client)


def upsert_chunks(
    collection,
    chunks: list[TextChunk],
    embeddings: list[list[float]],
) -> None:
    """
    Save chunks in Chroma.

    "upsert" = update if the id already exists, insert if it does not.
    So saving the same chunk twice never makes a duplicate.
    """

    if len(chunks) != len(embeddings):
        raise ValueError("Number of chunks and embeddings must match.")

    if not chunks:
        return

    collection.upsert(
        ids=[chunk.chunk_id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        embeddings=embeddings,
        metadatas=[
            {
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in chunks
        ],
    )


def search_chunks(
    collection,
    query_embedding: list[float],
    top_k: int = 5,
    where: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask Chroma for the chunks closest to the question."""

    if not query_embedding:
        raise ValueError("Query embedding cannot be empty.")

    if not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}.")

    total = collection.count()

    if total == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    return collection.query(
        query_embeddings=[query_embedding],
        # Never ask for more results than there are chunks.
        n_results=min(top_k, total),
        where=where,
        include=["documents", "metadatas", "distances"],
    )


def delete_document(collection, document_id: str) -> int:
    """Delete every chunk of one document. Returns how many were deleted."""

    if not document_id.strip():
        raise ValueError("document_id cannot be empty.")

    # include=[] means "give me only the ids".
    found = collection.get(
        where={"document_id": document_id},
        include=[],
    )

    ids = found["ids"]

    if ids:
        collection.delete(ids=ids)

    return len(ids)