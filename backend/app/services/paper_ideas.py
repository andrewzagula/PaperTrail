import json
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.llm import get_structured_client
from app.models.models import Paper
from app.models.models import PaperSection
from app.services.analyzer import analyze_paper
from app.workflows.idea_graph import (
    IdeaGraphNodes,
    IdeaGraphState,
    build_idea_graph,
)

NOT_EXPLICITLY_DISCUSSED = "Not explicitly discussed in the provided sources."
CANDIDATE_GENERATION_FALLBACK_WARNING = (
    "Candidate idea generation used deterministic fallback because model generation failed."
)
CRITIQUE_FALLBACK_WARNING = (
    "Idea critique used deterministic fallback because model critique failed."
)
INSUFFICIENT_FINAL_IDEAS_WARNING = (
    "Idea filtering returned fewer than 3 usable ideas."
)
MAX_IDEA_SOURCE_PAPERS = 5
MIN_CANDIDATE_IDEAS = 6
MAX_CANDIDATE_IDEAS = 8
MIN_FINAL_IDEAS = 3
MAX_FINAL_IDEAS = 5
MAX_IDEA_SECTION_CHARS = 60000
MAX_SECTION_CONTENT_CHARS = 6000

TRANSFORMATION_TYPES = ("combine", "ablate", "extend", "apply")

BREAKDOWN_FIELDS = (
    "problem",
    "method",
    "key_contributions",
    "results",
    "limitations",
    "future_work",
)

IDEA_SECTION_KEYWORDS = (
    "abstract",
    "introduction",
    "background",
    "related work",
    "method",
    "approach",
    "model",
    "architecture",
    "experiment",
    "evaluation",
    "dataset",
    "benchmark",
    "results",
    "discussion",
    "analysis",
    "limitation",
    "conclusion",
    "future",
)

IDEA_ITEM_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "transformation_type": {
            "type": "string",
            "enum": list(TRANSFORMATION_TYPES),
        },
        "description": {"type": "string"},
        "why_interesting": {"type": "string"},
        "feasibility": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "evidence_basis": {
            "type": "array",
            "items": {"type": "string"},
        },
        "risks_or_unknowns": {
            "type": "array",
            "items": {"type": "string"},
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "title",
        "transformation_type",
        "description",
        "why_interesting",
        "feasibility",
        "evidence_basis",
        "risks_or_unknowns",
        "warnings",
    ],
}

IDEA_CANDIDATES_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "items": IDEA_ITEM_JSON_SCHEMA,
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["candidates", "warnings"],
}

IDEA_CRITIQUE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ideas": {
            "type": "array",
            "items": IDEA_ITEM_JSON_SCHEMA,
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["ideas", "warnings"],
}


def generate_paper_ideas(
    db: Session,
    user_id: uuid.UUID,
    paper_ids: list[str] | None = None,
    topic: str | None = None,
) -> dict:
    normalized_ids, normalized_topic = validate_idea_sources(paper_ids, topic)
    graph = build_idea_graph(
        IdeaGraphNodes(
            load_sources=_idea_graph_load_sources,
            ensure_breakdowns=_idea_graph_ensure_breakdowns,
            normalize_context=_idea_graph_normalize_context,
            generate_candidates=_idea_graph_generate_candidates,
            critique_and_filter=_idea_graph_critique_and_filter,
            build_response=_idea_graph_build_response,
        )
    )
    result = graph.invoke({
        "db": db,
        "user_id": user_id,
        "paper_ids": normalized_ids,
        "topic": normalized_topic,
    })

    return {
        "selected_papers": result["selected_papers"],
        "source_topic": result["source_topic"],
        "ideas": result["ideas"],
        "warnings": result["warnings"],
    }


def validate_idea_sources(
    paper_ids: list[str] | None,
    topic: str | None,
) -> tuple[list[uuid.UUID], str | None]:
    normalized_topic = _normalize_topic(topic)
    normalized_ids = _normalize_paper_ids(paper_ids or [])

    if not normalized_ids and not normalized_topic:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one paper or topic to generate ideas.",
        )

    return normalized_ids, normalized_topic


def load_idea_papers_for_user(
    db: Session,
    user_id: uuid.UUID,
    paper_ids: list[uuid.UUID],
) -> list[Paper]:
    if not paper_ids:
        return []

    papers = (
        db.query(Paper)
        .filter(Paper.user_id == user_id, Paper.id.in_(paper_ids))
        .all()
    )
    papers_by_id = {paper.id: paper for paper in papers}

    missing_ids = [str(paper_id) for paper_id in paper_ids if paper_id not in papers_by_id]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Papers not found in your library: {', '.join(missing_ids)}",
        )

    return [papers_by_id[paper_id] for paper_id in paper_ids]


def _normalize_topic(topic: str | None) -> str | None:
    if topic is None:
        return None

    normalized_topic = topic.strip()
    return normalized_topic or None


def _normalize_paper_ids(paper_ids: list[str]) -> list[uuid.UUID]:
    if len(paper_ids) > MAX_IDEA_SOURCE_PAPERS:
        raise HTTPException(
            status_code=400,
            detail="You can use up to 5 papers for idea generation.",
        )

    normalized_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()

    for raw_id in paper_ids:
        try:
            paper_id = uuid.UUID(str(raw_id).strip())
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid paper ID: {raw_id}",
            )

        if paper_id in seen:
            raise HTTPException(
                status_code=400,
                detail="Duplicate paper IDs are not allowed.",
            )

        seen.add(paper_id)
        normalized_ids.append(paper_id)

    return normalized_ids


def _idea_graph_load_sources(state: IdeaGraphState) -> IdeaGraphState:
    return {
        "papers": load_idea_papers_for_user(
            state["db"],
            state["user_id"],
            state["paper_ids"],
        )
    }


def _idea_graph_ensure_breakdowns(state: IdeaGraphState) -> IdeaGraphState:
    db = state["db"]
    paper_contexts = []
    warnings = list(state.get("warnings", []))

    for paper in state.get("papers", []):
        sections = _load_sections_for_paper(db, paper.id)
        breakdown, breakdown_warnings = ensure_structured_breakdown(
            db,
            paper,
            sections,
        )
        paper_contexts.append({
            "paper": paper,
            "sections": sections,
            "breakdown": breakdown,
            "breakdown_warnings": breakdown_warnings,
        })
        warnings.extend(
            f"{paper.title}: {warning}"
            for warning in breakdown_warnings
        )

    return {
        "paper_contexts": paper_contexts,
        "warnings": _dedupe_strings(warnings),
    }


def _idea_graph_normalize_context(state: IdeaGraphState) -> IdeaGraphState:
    paper_contexts = state.get("paper_contexts", [])
    return {
        "selected_papers": [
            _serialize_selected_paper(paper_context["paper"])
            for paper_context in paper_contexts
        ],
        "source_topic": state.get("topic"),
        "idea_context": _build_idea_context(paper_contexts, state.get("topic")),
    }


def _idea_graph_generate_candidates(state: IdeaGraphState) -> IdeaGraphState:
    idea_context = state["idea_context"]
    try:
        payload = generate_candidate_ideas(idea_context)
        candidate_ideas = _normalize_idea_list(
            payload.get("candidates"),
            idea_context,
        )
        payload_warnings = _normalize_string_list(payload.get("warnings"))

        if len(candidate_ideas) < MIN_FINAL_IDEAS:
            raise ValueError("Candidate generation returned too few usable ideas.")
    except Exception:
        if not _can_build_deterministic_candidates(idea_context):
            raise

        candidate_ideas = _build_deterministic_candidate_ideas(idea_context)
        payload_warnings = [CANDIDATE_GENERATION_FALLBACK_WARNING]

    return {
        "candidate_ideas": candidate_ideas[:MAX_CANDIDATE_IDEAS],
        "warnings": _dedupe_strings([
            *state.get("warnings", []),
            *payload_warnings,
        ]),
    }


def _idea_graph_critique_and_filter(state: IdeaGraphState) -> IdeaGraphState:
    idea_context = state["idea_context"]
    candidate_ideas = state.get("candidate_ideas", [])
    try:
        payload = critique_and_filter_ideas(idea_context, candidate_ideas)
        ideas = _select_final_ideas(
            payload.get("ideas"),
            candidate_ideas,
            idea_context,
        )
        payload_warnings = _normalize_string_list(payload.get("warnings"))
    except Exception:
        ideas = candidate_ideas[:MAX_FINAL_IDEAS]
        payload_warnings = [CRITIQUE_FALLBACK_WARNING]

    if len(ideas) < MIN_FINAL_IDEAS:
        payload_warnings.append(INSUFFICIENT_FINAL_IDEAS_WARNING)

    return {
        "ideas": ideas[:MAX_FINAL_IDEAS],
        "warnings": _dedupe_strings([
            *state.get("warnings", []),
            *payload_warnings,
        ]),
    }


def _idea_graph_build_response(state: IdeaGraphState) -> IdeaGraphState:
    return {
        "ideas": state.get("ideas", [])[:MAX_FINAL_IDEAS],
        "warnings": _dedupe_strings(state.get("warnings", [])),
    }


def _serialize_selected_paper(paper: Paper) -> dict:
    return {
        "id": str(paper.id),
        "title": paper.title,
        "authors": paper.authors,
        "arxiv_url": paper.arxiv_url,
        "created_at": paper.created_at.isoformat() if paper.created_at else "",
    }


def ensure_structured_breakdown(
    db: Session,
    paper: Paper,
    sections: list[PaperSection],
) -> tuple[dict, list[str]]:
    if paper.structured_breakdown:
        return _normalize_breakdown(paper.structured_breakdown), []

    try:
        breakdown = analyze_paper(
            title=paper.title,
            abstract=paper.abstract or "",
            sections=[
                {"title": section.section_title, "content": section.content}
                for section in sections
            ],
        )
    except Exception as error:
        print(f"Warning: idea breakdown generation failed for paper {paper.id}: {error}")
        return _normalize_breakdown({}), [
            "Structured breakdown could not be generated automatically; idea generation used available metadata and sections."
        ]

    normalized_breakdown = _normalize_breakdown(breakdown)
    paper.structured_breakdown = normalized_breakdown
    db.commit()

    return normalized_breakdown, []


def generate_candidate_ideas(idea_context: dict[str, Any]) -> dict:
    context_json = json.dumps(idea_context, ensure_ascii=True)
    return _request_structured_json(
        model=settings.idea_generation_model,
        temperature=0.4,
        schema_name="idea_candidates",
        schema=IDEA_CANDIDATES_JSON_SCHEMA,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate bounded research idea candidates from supplied research "
                    "paper context and/or a user topic. Use only the provided context as the "
                    "evidence basis. Do not claim that a source paper proves something unless "
                    "it is present in the context.\n\n"
                    "Return exactly 6 to 8 candidate ideas as JSON. Include at least one idea "
                    "for each transformation type: combine, ablate, extend, and apply. "
                    "Each evidence_basis item must name a source paper, source section, or the "
                    "user topic. Put missing evidence or uncertainty in warnings."
                ),
            },
            {
                "role": "user",
                "content": f"Idea generation context:\n\n{context_json}",
            },
        ],
    )


def critique_and_filter_ideas(
    idea_context: dict[str, Any],
    candidate_ideas: list[dict[str, Any]],
) -> dict:
    context_json = json.dumps(idea_context, ensure_ascii=True)
    candidates_json = json.dumps(candidate_ideas, ensure_ascii=True)
    return _request_structured_json(
        model=settings.idea_critique_model,
        temperature=0.2,
        schema_name="idea_critique",
        schema=IDEA_CRITIQUE_JSON_SCHEMA,
        messages=[
            {
                "role": "system",
                "content": (
                    "You critique candidate research ideas and keep only the strongest, "
                    "least duplicate, most supportable ideas. Use only the supplied context "
                    "and candidate list. Preserve explicit uncertainty instead of inventing "
                    "support.\n\n"
                    "Return the best 3 to 5 ideas. Prefer a mix of transformation types when "
                    "quality permits. Remove ideas whose evidence basis is not grounded in a "
                    "source paper, source section, or the user topic."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Idea generation context:\n\n{context_json}\n\n"
                    f"Candidate ideas:\n\n{candidates_json}"
                ),
            },
        ],
    )


def _request_structured_json(
    model: str,
    temperature: float,
    schema_name: str,
    schema: dict,
    messages: list[dict[str, str]],
) -> dict:
    return get_structured_client().generate_structured(
        messages=messages,
        model=model,
        temperature=temperature,
        schema_name=schema_name,
        schema=schema,
    )


def _load_sections_for_paper(db: Session, paper_id: uuid.UUID) -> list[PaperSection]:
    return (
        db.query(PaperSection)
        .filter(PaperSection.paper_id == paper_id)
        .order_by(PaperSection.section_order)
        .all()
    )


def _build_idea_context(
    paper_contexts: list[dict[str, Any]],
    topic: str | None,
) -> dict[str, Any]:
    remaining_chars = MAX_IDEA_SECTION_CHARS
    papers = []

    for paper_context in paper_contexts:
        paper = paper_context["paper"]
        relevant_sections, remaining_chars = _build_relevant_section_items(
            paper_context["sections"],
            remaining_chars,
        )
        papers.append({
            "paper_id": str(paper.id),
            "title": paper.title,
            "authors": paper.authors or "",
            "abstract": paper.abstract or "",
            "breakdown": paper_context["breakdown"],
            "relevant_sections": relevant_sections,
            "warnings": paper_context["breakdown_warnings"],
        })

    return {
        "topic": topic,
        "papers": papers,
    }


def _build_relevant_section_items(
    sections: list[PaperSection],
    remaining_chars: int,
) -> tuple[list[dict[str, str]], int]:
    items = []

    for section in _select_relevant_sections(sections):
        if remaining_chars <= 0:
            break

        content = _clip_text(
            " ".join(section.content.split()),
            min(remaining_chars, MAX_SECTION_CONTENT_CHARS),
        )
        items.append({
            "title": section.section_title,
            "content": content,
        })
        remaining_chars -= len(section.section_title) + len(content)

    return items, remaining_chars


def _select_relevant_sections(sections: list[PaperSection]) -> list[PaperSection]:
    if not sections:
        return []

    selected_indices: list[int] = []
    seen_indices: set[int] = set()

    for index, section in enumerate(sections):
        title = section.section_title.lower()
        if (
            section.section_order <= 2
            or any(keyword in title for keyword in IDEA_SECTION_KEYWORDS)
        ) and index not in seen_indices:
            selected_indices.append(index)
            seen_indices.add(index)

    if not selected_indices:
        selected_indices = list(range(min(len(sections), 6)))

    return [sections[index] for index in selected_indices]


def _normalize_breakdown(breakdown: dict | None) -> dict:
    normalized = dict(breakdown or {})
    for field in BREAKDOWN_FIELDS:
        normalized[field] = _coerce_text(normalized.get(field), NOT_EXPLICITLY_DISCUSSED)
    return normalized


def _normalize_idea_list(
    value: object,
    idea_context: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    ideas = []
    for item in value:
        if isinstance(item, dict):
            ideas.append(_normalize_idea(item, idea_context))

    return ideas


def _normalize_idea(
    value: dict[str, Any],
    idea_context: dict[str, Any],
) -> dict[str, Any]:
    warnings = _normalize_string_list(value.get("warnings"))
    transformation_type = str(value.get("transformation_type", "")).strip().lower()
    if transformation_type not in TRANSFORMATION_TYPES:
        transformation_type = "extend"
        warnings.append("Transformation type was normalized to extend.")

    feasibility = str(value.get("feasibility", "")).strip().lower()
    if feasibility not in {"low", "medium", "high"}:
        feasibility = "medium"
        warnings.append("Feasibility was normalized to medium.")

    evidence_basis = _normalize_string_list(value.get("evidence_basis"))
    if not evidence_basis:
        evidence_basis = _fallback_evidence_basis(idea_context)
        warnings.append("Evidence basis was filled from the available source context.")

    risks_or_unknowns = _normalize_string_list(value.get("risks_or_unknowns"))
    if not risks_or_unknowns:
        risks_or_unknowns = ["Requires empirical validation against strong baselines."]

    return {
        "title": _coerce_text(value.get("title"), "Untitled research idea"),
        "transformation_type": transformation_type,
        "description": _coerce_text(
            value.get("description"),
            "Explore the proposed change using the supplied source context.",
        ),
        "why_interesting": _coerce_text(
            value.get("why_interesting"),
            "This could clarify whether the source approach transfers beyond its original setting.",
        ),
        "feasibility": feasibility,
        "evidence_basis": evidence_basis,
        "risks_or_unknowns": risks_or_unknowns,
        "warnings": _dedupe_strings(warnings),
    }


def _select_final_ideas(
    value: object,
    candidate_ideas: list[dict[str, Any]],
    idea_context: dict[str, Any],
) -> list[dict[str, Any]]:
    final_ideas = []
    seen_titles = set()
    normalized_ideas = _normalize_idea_list(value, idea_context)

    for idea in normalized_ideas:
        title_key = idea["title"].strip().lower()
        if not title_key or title_key in seen_titles:
            continue

        seen_titles.add(title_key)
        final_ideas.append(idea)
        if len(final_ideas) >= MAX_FINAL_IDEAS:
            return final_ideas

    if len(final_ideas) >= MIN_FINAL_IDEAS:
        return final_ideas

    for idea in candidate_ideas:
        title_key = idea["title"].strip().lower()
        if not title_key or title_key in seen_titles:
            continue

        seen_titles.add(title_key)
        final_ideas.append(idea)
        if len(final_ideas) >= MAX_FINAL_IDEAS:
            break

    return final_ideas


def _can_build_deterministic_candidates(idea_context: dict[str, Any]) -> bool:
    return bool(idea_context.get("papers"))


def _build_deterministic_candidate_ideas(
    idea_context: dict[str, Any],
) -> list[dict[str, Any]]:
    focus = _source_focus(idea_context)
    source_label = _source_label(idea_context)
    evidence_basis = _fallback_evidence_basis(idea_context)
    raw_ideas = [
        {
            "title": f"Combine {_clip_text(source_label, 60)} with complementary evidence",
            "transformation_type": "combine",
            "description": (
                f"Combine the source approach from {source_label} with an adjacent "
                f"method or evaluation signal to test whether it improves {focus}."
            ),
            "why_interesting": (
                "A combination study can reveal whether the source strengths are additive "
                "or only work under the original assumptions."
            ),
            "feasibility": "medium",
            "evidence_basis": evidence_basis,
            "risks_or_unknowns": [
                "The complementary method must be chosen carefully to avoid an unfair comparison."
            ],
            "warnings": [],
        },
        {
            "title": f"Ablate the core mechanism in {_clip_text(source_label, 60)}",
            "transformation_type": "ablate",
            "description": (
                f"Remove or vary the central mechanism described in {source_label} to "
                "identify which part drives the reported behavior."
            ),
            "why_interesting": (
                "Ablation can turn a broad paper insight into a sharper causal claim."
            ),
            "feasibility": "high",
            "evidence_basis": evidence_basis,
            "risks_or_unknowns": [
                "The available source context may not expose every implementation detail needed for a clean ablation."
            ],
            "warnings": [],
        },
        {
            "title": f"Extend {_clip_text(source_label, 60)} to a harder setting",
            "transformation_type": "extend",
            "description": (
                f"Extend the setting studied in {source_label} to a harder or less explored "
                f"version of {focus}."
            ),
            "why_interesting": (
                "A harder setting can test whether the reported approach is robust or narrowly scoped."
            ),
            "feasibility": "medium",
            "evidence_basis": evidence_basis,
            "risks_or_unknowns": [
                "The harder setting may require new data, baselines, or evaluation criteria."
            ],
            "warnings": [],
        },
        {
            "title": f"Apply {_clip_text(source_label, 60)} to {_clip_text(focus, 50)}",
            "transformation_type": "apply",
            "description": (
                f"Apply the source idea from {source_label} to {focus} and compare it "
                "against a simple task-appropriate baseline."
            ),
            "why_interesting": (
                "A targeted application can reveal whether the source idea has value outside its original setup."
            ),
            "feasibility": "medium",
            "evidence_basis": evidence_basis,
            "risks_or_unknowns": [
                "Transfer may fail if the new task violates assumptions in the source paper."
            ],
            "warnings": [],
        },
        {
            "title": f"Stress-test {_clip_text(source_label, 60)} under weak evidence",
            "transformation_type": "extend",
            "description": (
                f"Evaluate the source approach from {source_label} when supervision, context, "
                "or evaluation evidence is deliberately limited."
            ),
            "why_interesting": (
                "Weak-evidence settings expose whether the approach is practical in realistic research workflows."
            ),
            "feasibility": "medium",
            "evidence_basis": evidence_basis,
            "risks_or_unknowns": [
                "Results could be sensitive to the exact weak-evidence protocol."
            ],
            "warnings": [],
        },
        {
            "title": f"Replace one assumption in {_clip_text(source_label, 60)}",
            "transformation_type": "ablate",
            "description": (
                f"Replace a major assumption in {source_label} with a simpler or more "
                "realistic alternative, then measure how much performance or behavior changes."
            ),
            "why_interesting": (
                "Assumption replacement can uncover whether the idea depends on a fragile experimental setup."
            ),
            "feasibility": "high",
            "evidence_basis": evidence_basis,
            "risks_or_unknowns": [
                "The source context may not identify every assumption that matters."
            ],
            "warnings": [],
        },
    ]

    return [
        _normalize_idea(raw_idea, idea_context)
        for raw_idea in raw_ideas[:MIN_CANDIDATE_IDEAS]
    ]


def _source_focus(idea_context: dict[str, Any]) -> str:
    topic = _coerce_optional_text(idea_context.get("topic"))
    if topic:
        return topic

    for paper in idea_context.get("papers", []):
        problem = _coerce_optional_text(paper.get("breakdown", {}).get("problem"))
        if problem and problem != NOT_EXPLICITLY_DISCUSSED:
            return _clip_text(problem, 120)

    titles = [
        paper.get("title", "").strip()
        for paper in idea_context.get("papers", [])
        if paper.get("title", "").strip()
    ]
    return ", ".join(titles[:2]) or "the supplied research context"


def _source_label(idea_context: dict[str, Any]) -> str:
    titles = [
        paper.get("title", "").strip()
        for paper in idea_context.get("papers", [])
        if paper.get("title", "").strip()
    ]
    if len(titles) >= 2:
        return f"{titles[0]} and {titles[1]}"
    if titles:
        return titles[0]
    return _source_focus(idea_context)


def _fallback_evidence_basis(idea_context: dict[str, Any]) -> list[str]:
    evidence = []
    for paper in idea_context.get("papers", [])[:3]:
        title = paper.get("title", "").strip()
        sections = [
            section.get("title", "").strip()
            for section in paper.get("relevant_sections", [])[:2]
            if section.get("title", "").strip()
        ]
        if title and sections:
            evidence.append(f"{title}: {', '.join(sections)}")
        elif title:
            evidence.append(title)

    topic = _coerce_optional_text(idea_context.get("topic"))
    if topic:
        evidence.append(f"User topic: {topic}")

    return _dedupe_strings(evidence or ["Provided source context"])


def _coerce_text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _coerce_optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalize_string_list(value: object) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return _dedupe_strings(
        [str(item).strip() for item in value if str(item).strip()]
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    deduped = []

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)

    return deduped


def _clip_text(value: str, max_chars: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."
