import re
from pathlib import Path

import httpx

from app.config import settings
from app.services.errors import UserSafeServiceError

ARXIV_ID_PATTERN = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
ARXIV_PDF_URL = "https://arxiv.org/pdf/{paper_id}"
ARXIV_API_URL = "http://export.arxiv.org/api/query?id_list={paper_id}"
ARXIV_UNAVAILABLE_DETAIL = "Could not reach arXiv. Please try again."
ARXIV_NOT_FOUND_DETAIL = "No arXiv paper found for that ID."
ARXIV_REQUEST_FAILED_DETAIL = "arXiv request failed. Please try again."
ARXIV_INVALID_PDF_DETAIL = "arXiv returned an invalid PDF response."

PDF_DIR = settings.data_dir / "pdfs"
PDF_DIR.mkdir(exist_ok=True)


def extract_arxiv_id(url_or_id: str) -> str | None:
    match = ARXIV_ID_PATTERN.search(url_or_id)
    if match:
        return match.group(1)
    return None


async def fetch_arxiv_metadata(paper_id: str) -> dict:
    url = ARXIV_API_URL.format(paper_id=paper_id)
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.TimeoutException as error:
        raise UserSafeServiceError(503, ARXIV_UNAVAILABLE_DETAIL) from error
    except httpx.RequestError as error:
        raise UserSafeServiceError(503, ARXIV_UNAVAILABLE_DETAIL) from error
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise UserSafeServiceError(404, ARXIV_NOT_FOUND_DETAIL) from error
        raise UserSafeServiceError(502, ARXIV_REQUEST_FAILED_DETAIL) from error

    xml = resp.text
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    if not entries:
        raise UserSafeServiceError(404, ARXIV_NOT_FOUND_DETAIL)

    entry = entries[0]
    title = _extract_tag(entry, "title").strip().replace("\n", " ")

    authors = re.findall(r"<name>(.*?)</name>", entry)
    abstract = _extract_tag(entry, "summary").strip()

    return {
        "title": title,
        "authors": ", ".join(authors),
        "abstract": abstract,
        "arxiv_id": paper_id,
    }


async def download_arxiv_pdf(paper_id: str) -> Path:
    url = ARXIV_PDF_URL.format(paper_id=paper_id)
    pdf_path = PDF_DIR / f"{paper_id}.pdf"

    if pdf_path.exists():
        cached_content = pdf_path.read_bytes()
        if _is_pdf_content(cached_content):
            return pdf_path
        pdf_path.unlink()

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.TimeoutException as error:
        raise UserSafeServiceError(503, ARXIV_UNAVAILABLE_DETAIL) from error
    except httpx.RequestError as error:
        raise UserSafeServiceError(503, ARXIV_UNAVAILABLE_DETAIL) from error
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise UserSafeServiceError(404, ARXIV_NOT_FOUND_DETAIL) from error
        raise UserSafeServiceError(502, ARXIV_REQUEST_FAILED_DETAIL) from error

    if not _is_pdf_content(resp.content):
        raise UserSafeServiceError(502, ARXIV_INVALID_PDF_DETAIL)

    pdf_path.write_bytes(resp.content)
    return pdf_path


def _extract_tag(xml: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL)
    return match.group(1) if match else ""


def _is_pdf_content(content: bytes) -> bool:
    return content.lstrip().startswith(b"%PDF-")
