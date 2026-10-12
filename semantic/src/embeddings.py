# src/embeddings.py

from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"

MAX_TEXT_LENGTH = 10_000


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Load the embedding model once and reuse it.
    """

    return SentenceTransformer(MODEL_NAME)


def validate_texts(texts: list[str]) -> None:

    if not isinstance(texts, list):
        raise TypeError("texts must be a list.")

    for text in texts:

        if not isinstance(text, str):
            raise TypeError("Every text must be a string.")

        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError(
                "A text input is too large for embedding."
            )


def generate_embeddings(
    texts: list[str],
    batch_size: int = 32,
) -> list[list[float]]:
    """
    Convert multiple text chunks into embedding vectors.
    """

    validate_texts(texts)

    if not texts:
        return []

    if batch_size < 1 or batch_size > 128:
        raise ValueError(
            "batch_size must be between 1 and 128."
        )

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    return embeddings.tolist()


def generate_query_embedding(
    query: str,
) -> list[float]:
    """
    Convert one search query into an embedding.
    """

    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    if len(query) > MAX_TEXT_LENGTH:
        raise ValueError(
            "Search query is too long."
        )

    model = get_embedding_model()

    embedding = model.encode(
        [query],
        normalize_embeddings=True,
    )[0]

    return embedding.tolist()