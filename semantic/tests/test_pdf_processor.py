# semantic/tests/test_pdf_processor.py

import pymupdf
import pytest

from src.pdf_processor import (
    PdfProcessingError,
    calculate_file_hash,
    extract_pages,
)


def build_pdf(page_texts: list[str]) -> bytes:
    """Create a small real PDF in memory. An empty string = blank page."""

    document = pymupdf.open()

    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)

    data = document.tobytes()
    document.close()
    return data


def test_page_numbers_are_kept_and_blank_pages_skipped():
    data = build_pdf(["Hello first page", "", "Third page text"])

    result = extract_pages(data)

    assert result.page_count == 3
    assert [p.page_number for p in result.pages] == [1, 3]
    assert "Hello" in result.pages[0].text


def test_pdf_without_text_is_rejected():
    data = build_pdf(["", ""])

    with pytest.raises(PdfProcessingError) as error:
        extract_pages(data)

    assert error.value.code == "NO_EXTRACTABLE_TEXT"


def test_renamed_text_file_is_rejected():
    with pytest.raises(PdfProcessingError) as error:
        extract_pages(b"this is just plain text")

    assert error.value.code == "INVALID_PDF"


def test_corrupted_pdf_is_rejected():
    with pytest.raises(PdfProcessingError) as error:
        extract_pages(b"%PDF-1.4 this is garbage")

    assert error.value.code == "INVALID_PDF"


def test_oversized_pdf_is_rejected(monkeypatch):
    data = build_pdf(["small file"])

    # Pretend the limit is 0 MB so any file is "too large".
    monkeypatch.setattr("src.pdf_processor.MAX_FILE_SIZE_MB", 0)

    with pytest.raises(PdfProcessingError) as error:
        extract_pages(data)

    assert error.value.code == "FILE_TOO_LARGE"


def test_same_bytes_give_same_hash():
    assert calculate_file_hash(b"abc") == calculate_file_hash(b"abc")
    assert calculate_file_hash(b"abc") != calculate_file_hash(b"abd")