# semantic/tests/test_search.py

import pymupdf
import pytest

from src.chunker import TextChunk
from src.ingest import ingest_pdf_bytes
from src.pdf_processor import PdfProcessingError
from src.search import run_search
from src.vector_store import (
    delete_document,
    get_chroma_client,
    get_collection,
    search_chunks,
    upsert_chunks,
)


# Three fake "embeddings". Cosine distance from VEC_A:
#   VEC_A -> 0.0   VEC_C -> 0.2   VEC_B -> 1.0
VEC_A = [1.0, 0.0, 0.0]
VEC_B = [0.0, 1.0, 0.0]
VEC_C = [0.8, 0.6, 0.0]


@pytest.fixture
def collection(tmp_path):
    """A fresh, empty ChromaDB collection in a temporary folder."""

    client = get_chroma_client(tmp_path / "chroma")
    return get_collection(client, name="test_chunks")


def make_chunk(document_id, page, index, text):
    return TextChunk(
        chunk_id=f"{document_id}_p{page}_c{index}",
        document_id=document_id,
        filename=f"{document_id}.pdf",
        page_number=page,
        chunk_index=index,
        text=text,
    )


@pytest.fixture
def filled(collection):
    chunks = [
        make_chunk("doc1", 1, 0, "about cats"),
        make_chunk("doc1", 2, 0, "about dogs"),
        make_chunk("doc2", 5, 0, "about cats and dogs"),
    ]
    upsert_chunks(collection, chunks, [VEC_A, VEC_B, VEC_C])
    return collection


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


# ---------- ChromaDB storage and search ----------

def test_cosine_distance_is_used(filled):
    raw = search_chunks(filled, VEC_A, top_k=3)

    # Cosine gives 0.0, 0.2, 1.0. (Chroma's default, L2, would give
    # 0.0, 0.4, 2.0), so this proves our setting is working.
    assert raw["distances"][0] == pytest.approx([0.0, 0.2, 1.0], abs=1e-3)


def test_search_returns_contract_fields(filled, monkeypatch):
    monkeypatch.setattr("src.search.generate_query_embedding", lambda q: VEC_A)

    response = run_search("cats", collection=filled, max_distance=0.65)

    assert response["query"] == "cats"
    assert response["no_match"] is False
    assert [r["chunk_id"] for r in response["results"]] == [
        "doc1_p1_c0",
        "doc2_p5_c0",
    ]

    first = response["results"][0]
    assert first["document_id"] == "doc1"
    assert first["filename"] == "doc1.pdf"
    assert first["page_number"] == 1
    assert first["text"] == "about cats"
    assert first["distance"] == pytest.approx(0.0, abs=1e-3)


def test_far_results_give_no_match(filled, monkeypatch):
    monkeypatch.setattr(
        "src.search.generate_query_embedding", lambda q: [0.0, 0.0, 1.0]
    )

    response = run_search("unrelated", collection=filled, max_distance=0.65)

    assert response["no_match"] is True
    assert response["results"] == []


def test_search_can_filter_by_document(filled, monkeypatch):
    monkeypatch.setattr("src.search.generate_query_embedding", lambda q: VEC_A)

    response = run_search(
        "cats", document_id="doc2", collection=filled, max_distance=2
    )

    assert [r["document_id"] for r in response["results"]] == ["doc2"]


def test_empty_collection_gives_no_match(collection):
    response = run_search("anything", collection=collection)

    assert response["no_match"] is True
    assert response["results"] == []


def test_blank_query_is_rejected(collection):
    with pytest.raises(ValueError):
        run_search("   ", collection=collection)


def test_bad_top_k_is_rejected(filled):
    with pytest.raises(ValueError):
        run_search("cats", top_k=0, collection=filled)


def test_delete_document_removes_its_chunks(filled):
    removed = delete_document(filled, "doc1")

    assert removed == 2
    assert filled.count() == 1


def test_saving_same_chunk_twice_makes_no_duplicate(collection):
    chunk = make_chunk("doc1", 1, 0, "about cats")

    upsert_chunks(collection, [chunk], [VEC_A])
    upsert_chunks(collection, [chunk], [VEC_A])

    assert collection.count() == 1


# ---------- Ingest pipeline (with fake embeddings) ----------

def test_ingest_stores_chunks_with_metadata(collection, monkeypatch):
    monkeypatch.setattr("src.ingest.generate_embeddings", fake_embeddings)

    data = build_pdf(["First page about cats", "", "Third page about dogs"])

    result = ingest_pdf_bytes(data, "doc1", "report.pdf", collection=collection)

    assert result.page_count == 3
    assert result.chunk_count == 2

    stored = collection.get(where={"document_id": "doc1"}, include=["metadatas"])

    assert sorted(m["page_number"] for m in stored["metadatas"]) == [1, 3]
    assert all(m["filename"] == "report.pdf" for m in stored["metadatas"])


def test_reingest_replaces_old_chunks(collection, monkeypatch):
    monkeypatch.setattr("src.ingest.generate_embeddings", fake_embeddings)

    big = build_pdf(["Page one text", "Page two text", "Page three text"])
    small = build_pdf(["Only one page now"])

    ingest_pdf_bytes(big, "doc1", "a.pdf", collection=collection)
    assert collection.count() == 3

    ingest_pdf_bytes(small, "doc1", "a.pdf", collection=collection)
    assert collection.count() == 1  # old chunks are gone


def test_unsafe_document_id_is_rejected(collection):
    data = build_pdf(["some text"])

    with pytest.raises(ValueError):
        ingest_pdf_bytes(data, "../evil", "a.pdf", collection=collection)


def test_folders_are_removed_from_filename(collection, monkeypatch):
    monkeypatch.setattr("src.ingest.generate_embeddings", fake_embeddings)

    data = build_pdf(["some text"])

    result = ingest_pdf_bytes(
        data, "doc1", "C:\\secret\\folder\\report.pdf", collection=collection
    )

    assert result.filename == "report.pdf"


def test_scanned_pdf_is_not_indexed(collection, monkeypatch):
    monkeypatch.setattr("src.ingest.generate_embeddings", fake_embeddings)

    data = build_pdf(["", ""])

    with pytest.raises(PdfProcessingError):
        ingest_pdf_bytes(data, "doc1", "scan.pdf", collection=collection)

    assert collection.count() == 0