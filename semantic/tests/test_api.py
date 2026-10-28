# semantic/tests/test_api.py

import pymupdf
import pytest
from fastapi.testclient import TestClient

from src.main import app, get_collection_dependency
from src.vector_store import get_chroma_client, get_collection


VEC_A = [1.0, 0.0, 0.0]


def build_pdf(page_texts):
    document = pymupdf.open()

    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)

    data = document.tobytes()
    document.close()
    return data


def fake_embeddings(texts, batch_size=32, show_progress_bar=False):
    return [VEC_A for _ in texts]


@pytest.fixture
def client(tmp_path, monkeypatch):
    # No real model needed: use tiny fake embeddings.
    monkeypatch.setattr("src.ingest.generate_embeddings", fake_embeddings)
    monkeypatch.setattr("src.search.generate_query_embedding", lambda q: VEC_A)

    # Use a temporary ChromaDB instead of the real one.
    chroma = get_chroma_client(tmp_path / "chroma")
    test_collection = get_collection(chroma, name="test_api_chunks")
    app.dependency_overrides[get_collection_dependency] = lambda: test_collection

    # Not using "with": this skips the startup that loads the real model.
    # raise_server_exceptions=False lets us see the 500 response.
    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


def upload(client, data, document_id="doc1", filename="a.pdf"):
    return client.post(
        "/ingest",
        files={"file": (filename, data, "application/pdf")},
        data={"document_id": document_id, "filename": filename},
    )


def test_health_reports_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["chunk_count"] == 0


def test_ingest_search_delete_flow(client):
    pdf = build_pdf(["Cats are small animals"])

    ingest = upload(client, pdf)
    assert ingest.status_code == 200
    assert ingest.json()["chunk_count"] == 1
    assert ingest.json()["status"] == "indexed"

    found = client.post("/search", json={"query": "cats"})
    body = found.json()
    assert found.status_code == 200
    assert body["no_match"] is False
    assert body["results"][0]["filename"] == "a.pdf"
    assert body["results"][0]["page_number"] == 1
    assert body["results"][0]["document_id"] == "doc1"

    removed = client.delete("/documents/doc1")
    assert removed.status_code == 200
    assert removed.json()["deleted_chunks"] == 1

    after = client.post("/search", json={"query": "cats"})
    assert after.json()["no_match"] is True


def test_scanned_pdf_gives_clear_error(client):
    response = upload(client, build_pdf(["", ""]))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_EXTRACTABLE_TEXT"


def test_fake_pdf_is_rejected(client):
    response = upload(client, b"just some text")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PDF"


def test_unsafe_document_id_is_rejected(client):
    response = upload(client, build_pdf(["text"]), document_id="../evil")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_blank_query_is_rejected(client):
    response = client.post("/search", json={"query": "   "})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_missing_query_is_a_validation_error(client):
    response = client.post("/search", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_delete_with_bad_id_is_rejected(client):
    response = client.delete("/documents/bad$id")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unexpected_error_does_not_leak_details(client, monkeypatch):
    def explode(**kwargs):
        raise RuntimeError("secret C:\\private\\path")

    monkeypatch.setattr("src.main.run_search", explode)

    response = client.post("/search", json={"query": "cats"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in response.text