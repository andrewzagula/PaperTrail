from pathlib import Path

import fitz


def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def extract_metadata(pdf_path: Path) -> dict:
    doc = fitz.open(str(pdf_path))
    meta = doc.metadata or {}
    doc.close()

    title = (meta.get("title") or "").strip()
    author = (meta.get("author") or "").strip()

    return {
        "title": title,
        "authors": author,
    }
