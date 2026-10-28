# semantic/src/main.py

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Path, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import EMBEDDING_MODEL_NAME, MAX_FILE_SIZE_MB
from .embeddings import get_embedding_model
from .ingest import DOCUMENT_ID_PATTERN, ingest_pdf_bytes
from .pdf_processor import PdfProcessingError
from .search import run_search
from .vector_store import MAX_TOP_K, delete_document, get_default_collection


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("semantic")


# Only one ingest or delete may run at a time (so two uploads of the
# same document cannot mix their chunks). Searches are not blocked.
write_lock = threading.Lock()


# ---------------------------------------------------------------
# Startup
# ---------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts."""

    logger.info("Loading the embedding model and opening ChromaDB...")
    get_embedding_model()
    get_default_collection()
    logger.info("Semantic service is ready.")

    yield  # the server runs here


app = FastAPI(title="DocuMind Semantic Service", lifespan=lifespan)


def get_collection_dependency():
    """
    Gives each endpoint the ChromaDB collection.
    Tests replace this function with a temporary collection.
    """

    return get_default_collection()


# ---------------------------------------------------------------
# Request and response shapes (our API contract)
# ---------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    document_id: str | None = Field(default=None, max_length=64)
    top_k: int | None = Field(default=None, ge=1, le=MAX_TOP_K)


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    text: str
    distance: float


class SearchResponse(BaseModel):
    query: str
    no_match: bool
    message: str
    results: list[SearchResult]


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    status: str = "indexed"


class DeleteResponse(BaseModel):
    document_id: str
    deleted_chunks: int


class HealthResponse(BaseModel):
    status: str
    model: str
    chunk_count: int


# ---------------------------------------------------------------
# Errors: every error uses {"error": {"code": ..., "message": ...}}
# ---------------------------------------------------------------

PDF_ERROR_STATUS = {
    "FILE_TOO_LARGE": 413,
}


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.exception_handler(PdfProcessingError)
async def handle_pdf_error(request, error: PdfProcessingError):
    status_code = PDF_ERROR_STATUS.get(error.code, 422)
    return error_response(status_code, error.code, error.message)


@app.exception_handler(ValueError)
async def handle_value_error(request, error: ValueError):
    # Our own checks (bad document_id, blank query...) raise ValueError
    # with messages that are written to be safe to show.
    return error_response(422, "INVALID_REQUEST", str(error))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request, error: RequestValidationError):
    return error_response(
        422,
        "VALIDATION_ERROR",
        "The request is missing fields or has invalid values.",
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request, error: Exception):
    # The full details go to the server console only, never to the caller.
    logger.exception("Unexpected error")
    return error_response(
        500,
        "INTERNAL_ERROR",
        "Something went wrong in the semantic service.",
    )


# ---------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------
# These are plain "def" (not "async def"). FastAPI runs them in a
# separate thread, so slow work (embedding) does not freeze the server.

@app.get("/health", response_model=HealthResponse)
def health(collection=Depends(get_collection_dependency)):
    return HealthResponse(
        status="ok",
        model=EMBEDDING_MODEL_NAME,
        chunk_count=collection.count(),
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest(
    file: UploadFile = File(...),
    document_id: str = Form(...),
    filename: str = Form(...),
    collection=Depends(get_collection_dependency),
):
    # Read at most (limit + 1) bytes. If the file is bigger, the extra
    # byte makes the size check fail, and we never load a huge file.
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    data = file.file.read(max_bytes + 1)

    with write_lock:
        result = ingest_pdf_bytes(
            data, document_id, filename, collection=collection
        )

    return IngestResponse(
        document_id=result.document_id,
        filename=result.filename,
        page_count=result.page_count,
        chunk_count=result.chunk_count,
    )


@app.post("/search", response_model=SearchResponse)
def search(
    body: SearchRequest,
    collection=Depends(get_collection_dependency),
):
    return run_search(
        query=body.query,
        top_k=body.top_k,
        document_id=body.document_id,
        collection=collection,
    )


@app.delete("/documents/{document_id}", response_model=DeleteResponse)
def delete(
    document_id: str = Path(..., pattern=DOCUMENT_ID_PATTERN.pattern),
    collection=Depends(get_collection_dependency),
):
    with write_lock:
        removed = delete_document(collection, document_id)

    return DeleteResponse(document_id=document_id, deleted_chunks=removed)