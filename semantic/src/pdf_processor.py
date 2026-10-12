# src/pdf_processor.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib

import pymupdf


# -----------------------------
# Security / resource limits
# -----------------------------

MAX_FILE_SIZE_MB = 50
MAX_PAGES = 500
MAX_CHARS_PER_PAGE = 100_000


@dataclass(frozen=True)
class PageText:
    """
    Represents text extracted from one PDF page.
    """

    page_number: int
    text: str


def validate_pdf_path(pdf_path: Path, allowed_directory: Path) -> Path:
    """
    Validate that the PDF exists, is a regular file,
    stays inside the allowed directory, and is within
    the configured size limit.
    """

    pdf_path = pdf_path.resolve()
    allowed_directory = allowed_directory.resolve()

    # Prevent path traversal / access outside our PDF directory.
    try:
        pdf_path.relative_to(allowed_directory)
    except ValueError as exc:
        raise ValueError("PDF path is outside the allowed directory.") from exc

    if not pdf_path.is_file():
        raise FileNotFoundError("PDF file does not exist.")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are allowed.")

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    if pdf_path.stat().st_size > max_bytes:
        raise ValueError(
            f"PDF is too large. Maximum allowed size is "
            f"{MAX_FILE_SIZE_MB} MB."
        )

    return pdf_path


def calculate_file_hash(pdf_path: Path) -> str:
    """
    Generate a SHA-256 hash for the PDF.

    This gives us a stable identifier for duplicate detection.
    """

    sha256 = hashlib.sha256()

    with pdf_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def extract_pages(
    pdf_path: Path,
    allowed_directory: Path,
) -> tuple[str, list[PageText]]:
    """
    Extract text from a PDF page-by-page.

    Returns:
        (file_hash, list_of_pages)
    """

    pdf_path = validate_pdf_path(
        pdf_path,
        allowed_directory,
    )

    file_hash = calculate_file_hash(pdf_path)

    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:
        raise ValueError("Unable to open the PDF.") from exc

    try:
        # Reject encrypted PDFs for now.
        if document.is_encrypted:
            raise ValueError(
                "Encrypted/password-protected PDFs are not supported."
            )

        page_count = len(document)

        if page_count == 0:
            raise ValueError("The PDF contains no pages.")

        if page_count > MAX_PAGES:
            raise ValueError(
                f"PDF has too many pages. Maximum allowed is {MAX_PAGES}."
            )

        pages: list[PageText] = []

        for index, page in enumerate(document):

            # PDF page numbers shown to users start at 1.
            page_number = index + 1

            try:
                text = page.get_text("text", sort=True)
            except Exception as exc:
                raise ValueError(
                    f"Failed to extract text from page {page_number}."
                ) from exc

            text = text.strip()

            # Protect the pipeline from pathological pages.
            if len(text) > MAX_CHARS_PER_PAGE:
                text = text[:MAX_CHARS_PER_PAGE]

            if text:
                pages.append(
                    PageText(
                        page_number=page_number,
                        text=text,
                    )
                )

        return file_hash, pages

    finally:
        document.close()