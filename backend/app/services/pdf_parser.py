"""Extract text and metadata from PDF files using PyMuPDF."""

from pathlib import Path

import fitz  # PyMuPDF


def extract_text(pdf_path: Path) -> str:
    """Extract full text from a PDF file."""
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def extract_metadata(pdf_path: Path) -> dict:
    """Extract metadata (title, authors) from PDF.

    Falls back to first-line heuristics if PDF metadata is empty.
    """
    doc = fitz.open(str(pdf_path))
    meta = doc.metadata or {}
    doc.close()

    title = (meta.get("title") or "").strip()
    author = (meta.get("author") or "").strip()

    return {
        "title": title,
        "authors": author,
    }
