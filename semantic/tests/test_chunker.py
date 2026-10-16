# semantic/tests/test_chunker.py

import pytest

from src.chunker import create_chunks, split_text
from src.pdf_processor import PageText


def make_words(count: int) -> str:
    return " ".join(f"w{i}" for i in range(count))


def test_blank_text_gives_no_chunks():
    assert split_text("   \n  ") == []


def test_short_text_gives_one_chunk():
    chunks = split_text(make_words(10), chunk_size=50, overlap=10)
    assert len(chunks) == 1


def test_neighbouring_chunks_overlap():
    chunks = split_text(make_words(120), chunk_size=50, overlap=10)

    first = chunks[0].split()
    second = chunks[1].split()

    assert first[-10:] == second[:10]


def test_every_word_is_kept():
    chunks = split_text(make_words(120), chunk_size=50, overlap=10)

    seen = set()
    for chunk in chunks:
        seen.update(chunk.split())

    assert seen == {f"w{i}" for i in range(120)}


def test_overlap_not_smaller_than_chunk_size_is_rejected():
    with pytest.raises(ValueError):
        split_text("a b c", chunk_size=50, overlap=50)


def test_create_chunks_keeps_metadata():
    pages = [
        PageText(page_number=1, text=make_words(120)),
        PageText(page_number=3, text=make_words(10)),
    ]

    chunks = create_chunks(
        pages, "doc1", "a.pdf", chunk_size=50, overlap=10
    )

    assert len(chunks) == 4  # 3 chunks on page 1, 1 on page 3
    assert chunks[0].chunk_id == "doc1_p1_c0"
    assert chunks[-1].chunk_id == "doc1_p3_c0"
    assert chunks[-1].page_number == 3
    assert chunks[0].filename == "a.pdf"