# src/vector_store.py

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from .chunker import TextChunk


COLLECTION_NAME = "pdf_chunks"


def get_chroma_client(
    persist_directory: Path,
) -> chromadb.PersistentClient:
    """
    Create a persistent local Chroma client.
    """

    persist_directory = persist_directory.resolve()
    persist_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return chromadb.PersistentClient(
        path=str(persist_directory)
    )


def get_collection(
    client: chromadb.PersistentClient,
):
    """
    Get or create the PDF chunk collection.

    Cosine distance is used for semantic similarity.
    """

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={
            "hnsw": {
                "space": "cosine"
            }
        },
    )


def upsert_chunks(
    collection,
    chunks: list[TextChunk],
    embeddings: list[list[float]],
) -> None:
    """
    Store chunks, embeddings and metadata in Chroma.
    """

    if len(chunks) != len(embeddings):
        raise ValueError(
            "Number of chunks and embeddings must match."
        )

    if not chunks:
        return

    collection.upsert(
        ids=[
            chunk.chunk_id
            for chunk in chunks
        ],
        documents=[
            chunk.text
            for chunk in chunks
        ],
        embeddings=embeddings,
        metadatas=[
            {
                "document_id": chunk.document_id,
                "file_name": chunk.file_name,
                "page_number": chunk.page_number,
                "chunk_number": chunk.chunk_number,
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
    """
    Search Chroma for the most semantically similar chunks.
    """

    if not query_embedding:
        raise ValueError(
            "Query embedding cannot be empty."
        )

    if not 1 <= top_k <= 20:
        raise ValueError(
            "top_k must be between 1 and 20."
        )

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    return results


def delete_document(
    collection,
    document_id: str,
) -> None:
    """
    Delete all chunks belonging to a document.
    """

    if not document_id.strip():
        raise ValueError(
            "document_id cannot be empty."
        )

    collection.delete(
        where={
            "document_id": document_id
        }
    )