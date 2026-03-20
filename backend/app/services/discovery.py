"""Discovery orchestration: question → queries → search → rank."""

import json

from openai import OpenAI

from app.config import settings
from app.services.arxiv_searcher import ArxivResult, search_arxiv_multi

# Budget defaults
DEFAULT_MAX_QUERIES = 3
DEFAULT_MAX_RESULTS_PER_QUERY = 20
DEFAULT_MAX_RETURN = 10


async def generate_search_queries(question: str, max_queries: int = DEFAULT_MAX_QUERIES) -> list[str]:
    """Use LLM to generate targeted arXiv search queries from a research question."""
    client = OpenAI(api_key=settings.openai_api_key)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate arXiv search queries. Given a research question, "
                    "produce targeted keyword queries that would find relevant papers "
                    "on arXiv. Each query should use different angles or terminology "
                    "to maximize coverage. Output ONLY a JSON array of strings, "
                    "no other text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research question: {question}\n\n"
                    f"Generate exactly {max_queries} arXiv search queries as a JSON array. "
                    "Use specific technical terms. Vary terminology across queries."
                ),
            },
        ],
    )

    text = resp.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    queries = json.loads(text)
    if not isinstance(queries, list):
        raise ValueError("LLM did not return a JSON array")
    return [str(q) for q in queries[:max_queries]]


async def rank_results(
    question: str,
    results: list[ArxivResult],
    max_return: int = DEFAULT_MAX_RETURN,
) -> list[dict]:
    """Use LLM to rank and score search results by relevance to the question."""
    if not results:
        return []

    client = OpenAI(api_key=settings.openai_api_key)

    # Build papers list for the prompt
    papers_text = ""
    for i, r in enumerate(results):
        abstract_snippet = r.abstract[:500] if r.abstract else "No abstract"
        papers_text += (
            f"\n[{i}] Title: {r.title}\n"
            f"    Authors: {r.authors}\n"
            f"    Abstract: {abstract_snippet}\n"
        )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a research paper relevance ranker. Given a research question "
                    "and a list of papers, score each paper's relevance from 0.0 to 1.0 "
                    "and provide a brief reason. Output ONLY a JSON array of objects with "
                    "fields: index (int), score (float 0-1), reason (string, 1-2 sentences). "
                    "Sort by score descending. Only include the top papers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research question: {question}\n\n"
                    f"Papers:{papers_text}\n\n"
                    f"Rank these papers by relevance. Return the top {max_return} as JSON. "
                    "Be selective — only score above 0.5 if the paper is clearly relevant."
                ),
            },
        ],
    )

    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    rankings = json.loads(text)
    if not isinstance(rankings, list):
        raise ValueError("LLM did not return a JSON array")

    # Map back to results with scores
    ranked = []
    for rank_entry in rankings[:max_return]:
        idx = rank_entry.get("index", -1)
        if 0 <= idx < len(results):
            r = results[idx]
            ranked.append({
                "arxiv_id": r.arxiv_id,
                "title": r.title,
                "authors": r.authors,
                "abstract": r.abstract,
                "published": r.published,
                "relevance_score": float(rank_entry.get("score", 0)),
                "relevance_reason": rank_entry.get("reason", ""),
            })

    # Sort by score descending
    ranked.sort(key=lambda x: x["relevance_score"], reverse=True)
    return ranked


async def run_discovery(
    question: str,
    max_queries: int = DEFAULT_MAX_QUERIES,
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY,
    max_return: int = DEFAULT_MAX_RETURN,
) -> dict:
    """Full discovery pipeline: question → queries → search → rank.

    Returns dict with keys: queries, total_found, ranked_results, budget_used.
    """
    # Step 1: Generate queries
    queries = await generate_search_queries(question, max_queries=max_queries)

    # Step 2: Search arXiv
    all_results = await search_arxiv_multi(
        queries, max_results_per_query=max_results_per_query,
    )

    # Step 3: Rank results
    ranked = await rank_results(question, all_results, max_return=max_return)

    return {
        "queries": queries,
        "total_found": len(all_results),
        "ranked_results": ranked,
        "budget_used": {
            "queries_generated": len(queries),
            "total_papers_fetched": len(all_results),
            "papers_ranked": len(ranked),
        },
    }
