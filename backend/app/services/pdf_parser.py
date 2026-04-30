from pathlib import Path

import fitz

from app.services.errors import UserSafeServiceError

PDF_READ_ERROR_DETAIL = "Could not read PDF. The file may be corrupted or unsupported."


def extract_text(pdf_path: Path) -> str:
    doc = _open_pdf(pdf_path)
    try:
        pages = []
        for page in doc:
            pages.append(page.get_text())
        return "\n".join(pages)
    except Exception as error:
        raise UserSafeServiceError(422, PDF_READ_ERROR_DETAIL) from error
    finally:
        doc.close()


def extract_metadata(pdf_path: Path) -> dict:
    doc = _open_pdf(pdf_path)
    try:
        meta = doc.metadata or {}
    except Exception as error:
        raise UserSafeServiceError(422, PDF_READ_ERROR_DETAIL) from error
    finally:
        doc.close()

    title = (meta.get("title") or "").strip()
    author = (meta.get("author") or "").strip()

    return {
        "title": title,
        "authors": author,
    }


def _open_pdf(pdf_path: Path):
    try:
        doc = fitz.open(str(pdf_path))
        if doc.needs_pass:
            doc.close()
            raise UserSafeServiceError(422, PDF_READ_ERROR_DETAIL)
        return doc
    except UserSafeServiceError:
        raise
    except Exception as error:
        raise UserSafeServiceError(422, PDF_READ_ERROR_DETAIL) from error
