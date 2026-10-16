# semantic/src/pdf_processor.py

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .config import MAX_CHARS_PER_PAGE, MAX_FILE_SIZE_MB, MAX_PAGES


class PdfProcessingError(Exception):
    """
    A problem with a PDF that we can explain to the user.

    `code` is a short machine-readable label (the FastAPI layer will
    use it in the error JSON). `message` is safe to show to users.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PageText:
    """Text extracted from one PDF page."""

    page_number: int  # starts at 1, like a page number a person sees
    text: str


@dataclass(frozen=True)
class ExtractedPdf:
    """Result of reading a PDF."""

    page_count: int  # ALL pages, including blank ones
    pages: list[PageText]  # only pages that contain text


def _check_size(size_in_bytes: int) -> None:
    # Read the limit at call time so tests can change it.
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    if size_in_bytes > max_bytes:
        raise PdfProcessingError(
            "FILE_TOO_LARGE",
            f"PDF is too large. Maximum size is {MAX_FILE_SIZE_MB} MB.",
        )


def calculate_file_hash(data: bytes) -> str:
    """SHA-256 fingerprint of the file contents (used to detect duplicates)."""

    return hashlib.sha256(data).hexdigest()


def read_pdf_file(pdf_path: Path, allowed_directory: Path) -> bytes:
    """
    Read a PDF from disk, but ONLY from inside `allowed_directory`.
    Used by the command-line tools, not by the web API.
    """

    pdf_path = pdf_path.resolve()
    allowed_directory = allowed_directory.resolve()

    # Path-traversal protection: "..\\..\\secret.pdf" resolves to a
    # location outside the allowed folder and is rejected here.
    try:
        pdf_path.relative_to(allowed_directory)
    except ValueError:
        raise PdfProcessingError(
            "INVALID_PATH",
            "PDF path is outside the allowed directory.",
        ) from None

    if not pdf_path.is_file():
        raise PdfProcessingError(
            "FILE_NOT_FOUND", "PDF file does not exist."
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise PdfProcessingError(
            "INVALID_PDF", "Only .pdf files are allowed."
        )

    _check_size(pdf_path.stat().st_size)

    return pdf_path.read_bytes()


def extract_pages(data: bytes) -> ExtractedPdf:
    """
    Extract text from PDF bytes, page by page.

    Raises PdfProcessingError for oversized, fake, corrupted,
    password-protected, too-long, or scanned (no text) PDFs.
    """

    _check_size(len(data))

    # A real PDF contains the marker "%PDF-" near the start.
    # This catches a .txt file that was merely renamed to .pdf.
    if b"%PDF-" not in data[:1024]:
        raise PdfProcessingError(
            "INVALID_PDF", "The file is not a valid PDF."
        )

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise PdfProcessingError(
            "INVALID_PDF",
            "The PDF could not be opened. It may be corrupted.",
        ) from None

    # "with" guarantees document.close() runs, even if an error happens.
    with document:
        if document.needs_pass:
            raise PdfProcessingError(
                "ENCRYPTED_PDF",
                "Password-protected PDFs are not supported.",
            )

        page_count = document.page_count

        if page_count == 0:
            raise PdfProcessingError(
                "INVALID_PDF", "The PDF contains no pages."
            )

        if page_count > MAX_PAGES:
            raise PdfProcessingError(
                "TOO_MANY_PAGES",
                f"PDF has too many pages. Maximum is {MAX_PAGES}.",
            )

        pages: list[PageText] = []

        for index, page in enumerate(document):
            page_number = index + 1

            try:
                text = page.get_text("text", sort=True).strip()
            except Exception:
                raise PdfProcessingError(
                    "EXTRACTION_FAILED",
                    f"Failed to read text from page {page_number}.",
                ) from None

            # Resource guard against pathological pages.
            text = text[:MAX_CHARS_PER_PAGE]

            if text:
                pages.append(
                    PageText(page_number=page_number, text=text)
                )

    if not pages:
        raise PdfProcessingError(
            "NO_EXTRACTABLE_TEXT",
            "This PDF has no extractable text. "
            "It may be a scanned document.",
        )

    return ExtractedPdf(page_count=page_count, pages=pages)