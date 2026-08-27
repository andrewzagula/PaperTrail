import asyncio
import re
from pathlib import Path

import httpx

from app.config import settings
from app.services.errors import UserSafeServiceError

ARXIV_ID_PATTERN = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
ARXIV_ABS_URL = "https://arxiv.org/abs/{paper_id}"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{paper_id}"
ARXIV_API_URL = "http://export.arxiv.org/api/query?id_list={paper_id}"
ARXIV_UNAVAILABLE_DETAIL = "Could not reach arXiv. Please try again."
ARXIV_NOT_FOUND_DETAIL = "No arXiv paper found for that ID."
ARXIV_REQUEST_FAILED_DETAIL = "arXiv request failed. Please try again."
ARXIV_INVALID_PDF_DETAIL = "arXiv returned an invalid PDF response."

PDF_DIR = settings.data_dir / "pdfs"
PDF_DIR.mkdir(exist_ok=True)

# arXiv throttles by IP and answers 429 without warning. A discovery run makes
# several requests in sequence, so a single throttle used to fail the whole
# run. Retry the transient statuses with exponential backoff, honouring
# Retry-After when arXiv sends it.
ARXIV_MAX_ATTEMPTS = 3
ARXIV_RETRY_BASE_DELAY = 2.0
ARXIV_RETRY_MAX_DELAY = 20.0
ARXIV_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _retry_delay(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return min(float(retry_after), ARXIV_RETRY_MAX_DELAY)
        except ValueError:
            pass
    return min(ARXIV_RETRY_BASE_DELAY * (2 ** (attempt - 1)), ARXIV_RETRY_MAX_DELAY)


async def arxiv_get(
    url: str,
    *,
    params: dict | None = None,
    timeout: float = 30.0,
    not_found_on_404: bool = False,
) -> httpx.Response:
    """GET an arXiv URL, retrying transient failures.

    Permanent failures (404, malformed query) raise immediately; retrying them
    would only delay the error the caller already needs to see.
    """
    last_error: Exception | None = None

    for attempt in range(1, ARXIV_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                # Only pass params when there are any, so a bare GET keeps the
                # same call shape it had before retries were introduced.
                resp = await (
                    client.get(url, params=params) if params else client.get(url)
                )
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if not_found_on_404 and status == 404:
                raise UserSafeServiceError(404, ARXIV_NOT_FOUND_DETAIL) from error
            if status not in ARXIV_RETRYABLE_STATUS or attempt == ARXIV_MAX_ATTEMPTS:
                raise UserSafeServiceError(
                    502, ARXIV_REQUEST_FAILED_DETAIL
                ) from error
            last_error = error
            await asyncio.sleep(
                _retry_delay(attempt, error.response.headers.get("retry-after"))
            )
        except httpx.RequestError as error:
            # Covers timeouts, connection resets and DNS failures.
            if attempt == ARXIV_MAX_ATTEMPTS:
                raise UserSafeServiceError(503, ARXIV_UNAVAILABLE_DETAIL) from error
            last_error = error
            await asyncio.sleep(_retry_delay(attempt, None))

    raise UserSafeServiceError(503, ARXIV_UNAVAILABLE_DETAIL) from last_error


def extract_arxiv_id(url_or_id: str) -> str | None:
    match = ARXIV_ID_PATTERN.search(url_or_id)
    if match:
        return match.group(1)
    return None


async def fetch_arxiv_metadata(paper_id: str) -> dict:
    url = ARXIV_API_URL.format(paper_id=paper_id)
    resp = await arxiv_get(url, timeout=30, not_found_on_404=True)

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

    resp = await arxiv_get(url, timeout=60, not_found_on_404=True)

    if not _is_pdf_content(resp.content):
        raise UserSafeServiceError(502, ARXIV_INVALID_PDF_DETAIL)

    pdf_path.write_bytes(resp.content)
    return pdf_path


def _extract_tag(xml: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL)
    return match.group(1) if match else ""


def _is_pdf_content(content: bytes) -> bool:
    return content.lstrip().startswith(b"%PDF-")
