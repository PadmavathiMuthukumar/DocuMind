# semantic/src/embeddings.py

from __future__ import annotations

from functools import lru_cache

from .config import EMBEDDING_MODEL_NAME


MAX_TEXT_LENGTH = 10_000  # characters


@lru_cache(maxsize=1)
def get_embedding_model():
    """
    Load the embedding model ONE time and reuse it.

    Loading takes seconds, so we never want to do it on every request.
    The first time ever, the model is downloaded (about 90 MB) and
    saved on your computer. After that it loads from disk.
    """

    # We import here (not at the top of the file) so that importing
    # this file is fast. The heavy library only loads when really needed.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def validate_texts(texts: list[str]) -> None:
    if not isinstance(texts, list):
        raise TypeError("texts must be a list.")

    for text in texts:
        if not isinstance(text, str):
            raise TypeError("Every text must be a string.")

        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError("A text input is too large for embedding.")


def generate_embeddings(
    texts: list[str],
    batch_size: int = 32,
    show_progress_bar: bool = False,
) -> list[list[float]]:
    """Turn many chunk texts into embeddings (one list of numbers each)."""

    validate_texts(texts)

    if not texts:
        return []

    if not 1 <= batch_size <= 128:
        raise ValueError("batch_size must be between 1 and 128.")

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress_bar,
        # Normalized = every vector has length 1. This makes cosine
        # distance behave nicely and consistently.
        normalize_embeddings=True,
    )

    return embeddings.tolist()


def generate_query_embedding(query: str) -> list[float]:
    """Turn one search question into an embedding (same model as chunks)."""

    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    if len(query) > MAX_TEXT_LENGTH:
        raise ValueError("Search query is too long.")

    model = get_embedding_model()

    embedding = model.encode([query], normalize_embeddings=True)[0]

    return embedding.tolist()