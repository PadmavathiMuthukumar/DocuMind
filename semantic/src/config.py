# semantic/src/config.py

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# This file is semantic/src/config.py, so two ".parent" calls
# take us up to the semantic/ folder.
SEMANTIC_ROOT = Path(__file__).resolve().parent.parent

# Read semantic/.env if it exists. If it doesn't, we just use defaults.
load_dotenv(SEMANTIC_ROOT / ".env")


def _read_str(name: str, default: str) -> str:
    raw = os.getenv(name, "").strip()
    return raw or default


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()

    if not raw:
        return default

    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"{name} must be a whole number, got {raw!r}."
        ) from None


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()

    if not raw:
        return default

    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"{name} must be a number, got {raw!r}."
        ) from None


def _read_path(name: str, default: str) -> Path:
    path = Path(_read_str(name, default))

    # Relative paths are relative to semantic/, not to wherever
    # the terminal happens to be.
    if not path.is_absolute():
        path = SEMANTIC_ROOT / path

    return path.resolve()


# ---- Embeddings ----
EMBEDDING_MODEL_NAME = _read_str(
    "EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2"
)

# ---- Chunking (counted in words) ----
CHUNK_SIZE_WORDS = _read_int("CHUNK_SIZE_WORDS", 150)
CHUNK_OVERLAP_WORDS = _read_int("CHUNK_OVERLAP_WORDS", 30)

# ---- PDF safety limits ----
MAX_FILE_SIZE_MB = _read_int("MAX_FILE_SIZE_MB", 50)
MAX_PAGES = _read_int("MAX_PAGES", 500)
MAX_CHARS_PER_PAGE = _read_int("MAX_CHARS_PER_PAGE", 100_000)

# ---- Storage ----
PDF_DIRECTORY = _read_path("PDF_DIR", "data/pdfs")
CHROMA_DIRECTORY = _read_path("CHROMA_DIR", "data/chroma")
COLLECTION_NAME = _read_str("COLLECTION_NAME", "pdf_chunks")

# ---- Search ----
TOP_K_DEFAULT = _read_int("TOP_K_DEFAULT", 5)
MAX_DISTANCE = _read_float("MAX_DISTANCE", 0.65)