"""Fetch papers from arXiv given a URL or paper ID."""

import re
from pathlib import Path

import httpx

from app.config import settings

ARXIV_ID_PATTERN = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
ARXIV_PDF_URL = "https://arxiv.org/pdf/{paper_id}"
ARXIV_API_URL = "http://export.arxiv.org/api/query?id_list={paper_id}"

PDF_DIR = settings.data_dir / "pdfs"
PDF_DIR.mkdir(exist_ok=True)


def extract_arxiv_id(url_or_id: str) -> str | None:
    """Extract arXiv paper ID from a URL or raw ID string.

    Handles:
        - https://arxiv.org/abs/2301.00001
        - https://arxiv.org/pdf/2301.00001
        - https://arxiv.org/abs/2301.00001v2
        - 2301.00001
    """
    match = ARXIV_ID_PATTERN.search(url_or_id)
    if match:
        return match.group(1)
    return None


async def fetch_arxiv_metadata(paper_id: str) -> dict:
    """Fetch title, authors, and abstract from the arXiv API."""
    url = ARXIV_API_URL.format(paper_id=paper_id)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    xml = resp.text

    # Simple XML parsing — arXiv Atom feed
    title = _extract_tag(xml, "title")
    # First <title> is the feed title ("ArXiv Query:..."), second is the paper
    titles = re.findall(r"<title[^>]*>(.*?)</title>", xml, re.DOTALL)
    title = titles[-1].strip().replace("\n", " ") if len(titles) > 1 else ""

    authors = re.findall(r"<name>(.*?)</name>", xml)
    abstract = _extract_tag(xml, "summary").strip()

    return {
        "title": title,
        "authors": ", ".join(authors),
        "abstract": abstract,
        "arxiv_id": paper_id,
    }


async def download_arxiv_pdf(paper_id: str) -> Path:
    """Download the PDF from arXiv and save to data/pdfs/."""
    url = ARXIV_PDF_URL.format(paper_id=paper_id)
    pdf_path = PDF_DIR / f"{paper_id}.pdf"

    if pdf_path.exists():
        return pdf_path

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    pdf_path.write_bytes(resp.content)
    return pdf_path


def _extract_tag(xml: str, tag: str) -> str:
    """Extract first occurrence of a tag's text content."""
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL)
    return match.group(1) if match else ""
