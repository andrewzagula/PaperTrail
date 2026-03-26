import asyncio
import re
from dataclasses import dataclass

import httpx

ARXIV_SEARCH_URL = "http://export.arxiv.org/api/query"
RATE_LIMIT_DELAY = 3.0


@dataclass
class ArxivResult:
    arxiv_id: str
    title: str
    authors: str
    abstract: str
    published: str


async def search_arxiv(query: str, max_results: int = 20) -> list[ArxivResult]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(max_results, 50),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(ARXIV_SEARCH_URL, params=params)
        resp.raise_for_status()

    return _parse_atom_feed(resp.text)


async def search_arxiv_multi(
    queries: list[str],
    max_results_per_query: int = 20,
) -> list[ArxivResult]:
    all_results: list[ArxivResult] = []
    seen_ids: set[str] = set()

    for i, query in enumerate(queries):
        if i > 0:
            await asyncio.sleep(RATE_LIMIT_DELAY)

        results = await search_arxiv(query, max_results=max_results_per_query)
        for r in results:
            if r.arxiv_id not in seen_ids:
                seen_ids.add(r.arxiv_id)
                all_results.append(r)

    return all_results


def _parse_atom_feed(xml: str) -> list[ArxivResult]:
    results = []
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)

    for entry in entries:
        arxiv_id = _extract_arxiv_id(entry)
        if not arxiv_id:
            continue

        titles = re.findall(r"<title[^>]*>(.*?)</title>", entry, re.DOTALL)
        title = titles[0].strip().replace("\n", " ") if titles else ""

        authors = re.findall(r"<name>(.*?)</name>", entry)
        abstract_match = re.search(
            r"<summary[^>]*>(.*?)</summary>", entry, re.DOTALL
        )
        abstract = abstract_match.group(1).strip() if abstract_match else ""

        published_match = re.search(
            r"<published>(.*?)</published>", entry
        )
        published = published_match.group(1)[:10] if published_match else ""

        results.append(ArxivResult(
            arxiv_id=arxiv_id,
            title=title,
            authors=", ".join(authors),
            abstract=abstract,
            published=published,
        ))

    return results


def _extract_arxiv_id(entry_xml: str) -> str | None:
    id_match = re.search(r"<id>.*?/abs/(\d{4}\.\d{4,5})(v\d+)?</id>", entry_xml)
    return id_match.group(1) if id_match else None
