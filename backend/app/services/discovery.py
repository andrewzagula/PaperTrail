from app.config import settings
from app.llm import get_structured_client
from app.services.arxiv_searcher import ArxivResult, search_arxiv_multi

DEFAULT_MAX_QUERIES = 3
DEFAULT_MAX_RESULTS_PER_QUERY = 20
DEFAULT_MAX_RETURN = 10
MIN_UNIQUE_RESULTS_FOR_COVERAGE = 5
MIN_RESULTS_BUDGET_FOR_COVERAGE = 5
HIGH_CONFIDENCE_RELEVANCE_THRESHOLD = 0.60

FEWER_QUERIES_WARNING = (
    "Generated fewer usable queries than requested; discovery coverage may be narrow."
)
NO_UNIQUE_RESULTS_WARNING = (
    "arXiv returned no unique papers for the generated queries."
)
LOW_UNIQUE_RESULTS_WARNING = (
    "arXiv returned very few unique papers; discovery coverage is low."
)
NO_HIGH_CONFIDENCE_RESULTS_WARNING = (
    "No high-confidence discovery matches were found; review low-score results carefully."
)
SMALL_RESULT_BUDGET_WARNING = (
    "Discovery result budget is small; coverage may be too narrow for broad coverage."
)
QUERY_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "queries": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["queries"],
}
RANKING_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rankings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer"},
                    "score": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["index", "score", "reason"],
            },
        },
    },
    "required": ["rankings"],
}


def _normalize_queries(queries: object, max_queries: int) -> list[str]:
    normalized = []
    seen = set()

    if not isinstance(queries, list):
        return normalized

    for query in queries:
        if query is None:
            continue
        stripped = str(query).strip()
        if not stripped:
            continue
        key = " ".join(stripped.split()).casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(stripped)
        if len(normalized) >= max_queries:
            break

    return normalized


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for warning in warnings:
        if warning in seen:
            continue
        seen.add(warning)
        deduped.append(warning)
    return deduped


def _build_discovery_warnings(
    queries: list[str],
    max_queries: int,
    total_found: int,
    ranked_results: list[dict],
    max_return: int,
) -> list[str]:
    warnings = []

    if len(queries) < max_queries:
        warnings.append(FEWER_QUERIES_WARNING)

    if total_found == 0:
        warnings.append(NO_UNIQUE_RESULTS_WARNING)
    elif total_found < MIN_UNIQUE_RESULTS_FOR_COVERAGE:
        warnings.append(LOW_UNIQUE_RESULTS_WARNING)

    if ranked_results:
        max_score = max(
            float(result.get("relevance_score") or 0) for result in ranked_results
        )
        if max_score < HIGH_CONFIDENCE_RELEVANCE_THRESHOLD:
            warnings.append(NO_HIGH_CONFIDENCE_RESULTS_WARNING)

    if max_return < MIN_RESULTS_BUDGET_FOR_COVERAGE:
        warnings.append(SMALL_RESULT_BUDGET_WARNING)

    return _dedupe_warnings(warnings)


async def generate_search_queries(question: str, max_queries: int = DEFAULT_MAX_QUERIES) -> list[str]:
    payload = get_structured_client().generate_structured(
        model=settings.discovery_query_model,
        temperature=0.3,
        schema_name="discovery_queries",
        schema=QUERY_RESPONSE_JSON_SCHEMA,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate arXiv search queries. Given a research question, "
                    "produce targeted keyword queries that would find relevant papers "
                    "on arXiv. Each query should use different angles or terminology "
                    "to maximize coverage. Return a JSON object with a single "
                    '"queries" field containing an array of strings.'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research question: {question}\n\n"
                    f"Generate exactly {max_queries} arXiv search queries inside the "
                    '"queries" array. Use specific technical terms. Vary terminology across '
                    "queries."
                ),
            },
        ],
    )

    return _normalize_queries(payload.get("queries", []), max_queries)


async def rank_results(
    question: str,
    results: list[ArxivResult],
    max_return: int = DEFAULT_MAX_RETURN,
) -> list[dict]:
    if not results:
        return []

    papers_text = ""
    for i, r in enumerate(results):
        abstract_snippet = r.abstract[:500] if r.abstract else "No abstract"
        papers_text += (
            f"\n[{i}] Title: {r.title}\n"
            f"    Authors: {r.authors}\n"
            f"    Abstract: {abstract_snippet}\n"
        )

    payload = get_structured_client().generate_structured(
        model=settings.discovery_rank_model,
        temperature=0.1,
        schema_name="discovery_rankings",
        schema=RANKING_RESPONSE_JSON_SCHEMA,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a research paper relevance ranker. Given a research question "
                    "and a list of papers, score each paper's relevance from 0.0 to 1.0 "
                    "and provide a brief reason. Return a JSON object with a single "
                    '"rankings" field containing an array of objects with fields: index '
                    "(int), score (float 0-1), reason (string, 1-2 sentences). Sort by "
                    "score descending. Only include the top papers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research question: {question}\n\n"
                    f"Papers:{papers_text}\n\n"
                    f"Rank these papers by relevance. Return the top {max_return} inside the "
                    '"rankings" array. Be selective - only score above 0.5 if the paper is '
                    "clearly relevant."
                ),
            },
        ],
    )

    ranked = []
    for rank_entry in payload.get("rankings", [])[:max_return]:
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

    ranked.sort(key=lambda x: x["relevance_score"], reverse=True)
    return ranked


async def run_discovery(
    question: str,
    max_queries: int = DEFAULT_MAX_QUERIES,
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY,
    max_return: int = DEFAULT_MAX_RETURN,
) -> dict:
    queries = await generate_search_queries(question, max_queries=max_queries)

    all_results = await search_arxiv_multi(
        queries, max_results_per_query=max_results_per_query,
    )

    ranked = await rank_results(question, all_results, max_return=max_return)
    warnings = _build_discovery_warnings(
        queries=queries,
        max_queries=max_queries,
        total_found=len(all_results),
        ranked_results=ranked,
        max_return=max_return,
    )

    return {
        "queries": queries,
        "total_found": len(all_results),
        "ranked_results": ranked,
        "warnings": warnings,
        "budget_used": {
            "queries_generated": len(queries),
            "total_papers_fetched": len(all_results),
            "papers_ranked": len(ranked),
            "max_results_requested": max_return,
            "warnings": warnings,
        },
    }
