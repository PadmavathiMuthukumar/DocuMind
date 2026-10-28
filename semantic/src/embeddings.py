# semantic/src/embeddings.py

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .config import EMBEDDING_MODEL_NAME


MAX_TEXT_LENGTH = 10_000  # characters

# The ONNX version below supports only this model.
SUPPORTED_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model():
    """
    Load the embedding model ONE time and reuse it.

    This uses ChromaDB's built-in ONNX version of all-MiniLM-L6-v2.
    It runs with onnxruntime, so it does not need torch (which
    Windows Application Control blocks on this computer).
    """

    if EMBEDDING_MODEL_NAME != SUPPORTED_MODEL_NAME:
        raise ValueError(
            f"EMBEDDING_MODEL_NAME must be '{SUPPORTED_MODEL_NAME}' "
            f"in this ONNX version, but it is '{EMBEDDING_MODEL_NAME}'."
        )

    # Imported here so that importing this file stays fast.
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    model = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])

    # Embed one tiny text now. This downloads the model file on the very
    # first run and prepares everything, so real requests are not slow
    # and two requests cannot start the download at the same time.
    model(["warm up"])

    return model


def validate_texts(texts: list[str]) -> None:
    if not isinstance(texts, list):
        raise TypeError("texts must be a list.")

    for text in texts:
        if not isinstance(text, str):
            raise TypeError("Every text must be a string.")

        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError("A text input is too large for embedding.")


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Turn many chunk texts into embeddings (384 numbers each)."""

    validate_texts(texts)

    if not texts:
        return []

    model = get_embedding_model()

    vectors = model(texts)

    # Convert numpy arrays into plain Python lists of numbers,
    # which is what ChromaDB and JSON expect.
    return np.asarray(vectors, dtype="float32").tolist()


def generate_query_embedding(query: str) -> list[float]:
    """Turn one search question into an embedding (same model as chunks)."""

    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    if len(query) > MAX_TEXT_LENGTH:
        raise ValueError("Search query is too long.")

    model = get_embedding_model()

    vectors = model([query])

    return np.asarray(vectors[0], dtype="float32").tolist()