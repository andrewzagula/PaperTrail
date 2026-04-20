import json
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.llm import get_structured_client
from app.models.models import Paper, PaperSection
from app.services.analyzer import analyze_paper

NOT_EXPLICITLY_DISCUSSED = "Not explicitly discussed in the paper."
NOT_EXPLICITLY_DISCUSSED_ACROSS_PAPERS = (
    "Not explicitly discussed across the selected papers."
)
MAX_COMPARE_SECTION_CHARS = 50000

BREAKDOWN_FIELDS = {
    "problem": "problem",
    "method": "method",
    "key_contributions": "key_contributions",
    "results": "results",
    "limitations": "limitations",
    "future_work": "future_work",
}

COMPARE_FIELDS = (
    "problem",
    "method",
    "dataset_or_eval_setup",
    "key_results",
    "strengths",
    "weaknesses",
)

COMPARE_FIELD_LABELS = {
    "problem": "Problem",
    "method": "Method",
    "dataset_or_eval_setup": "Dataset / Eval Setup",
    "key_results": "Key Results",
    "strengths": "Strengths",
    "weaknesses": "Weaknesses",
}

SUMMARY_FIELDS = (
    "problem_landscape",
    "method_divergence",
    "evaluation_differences",
    "researcher_tradeoffs",
)

SUMMARY_FIELD_LABELS = {
    "problem_landscape": "What the papers are trying to solve",
    "method_divergence": "Where the methods diverge",
    "evaluation_differences": "How evaluation differs",
    "researcher_tradeoffs": "Researcher tradeoffs",
}

SECTION_KEYWORDS = (
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
)

EVIDENCE_SECTION_HINTS = {
    "problem": ("abstract", "introduction", "background", "related work"),
    "method": ("method", "approach", "model", "architecture"),
    "dataset_or_eval_setup": ("dataset", "evaluation", "benchmark", "experiment"),
    "key_results": ("results", "evaluation", "experiment", "analysis", "discussion"),
    "strengths": ("abstract", "results", "discussion", "conclusion"),
    "weaknesses": ("limitation", "discussion", "analysis", "conclusion"),
}

COMPARE_PROFILE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        **{
            field: {"type": "string"}
            for field in COMPARE_FIELDS
        },
        "evidence_notes": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                field: {
                    "type": "array",
                    "items": {"type": "string"},
                }
                for field in COMPARE_FIELDS
            },
            "required": list(COMPARE_FIELDS),
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [*COMPARE_FIELDS, "evidence_notes", "warnings"],
}

COMPARE_SYNTHESIS_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        **{
            field: {"type": "string"}
            for field in SUMMARY_FIELDS
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [*SUMMARY_FIELDS, "warnings"],
}


def compare_papers(db: Session, user_id: uuid.UUID, paper_ids: list[str]) -> dict:
    normalized_ids = validate_compare_paper_ids(paper_ids)
    papers = load_papers_for_user(db, user_id, normalized_ids)

    selected_papers = []
    normalized_profiles = []

    for paper in papers:
        sections = _load_sections_for_paper(db, paper.id)
        breakdown, breakdown_warnings = ensure_structured_breakdown(db, paper, sections)
        profile = normalize_paper_for_compare(
            paper=paper,
            breakdown=breakdown,
            sections=sections,
            seed_warnings=breakdown_warnings,
        )

        selected_papers.append({
            "id": str(paper.id),
            "title": paper.title,
            "authors": paper.authors,
            "arxiv_url": paper.arxiv_url,
            "created_at": paper.created_at.isoformat() if paper.created_at else "",
        })
        normalized_profiles.append(profile)

    narrative_summary, summary_warnings = build_comparison_narrative(normalized_profiles)
    warnings = _dedupe_strings(
        _collect_top_level_warnings(normalized_profiles) + summary_warnings
    )

    return {
        "selected_papers": selected_papers,
        "normalized_profiles": normalized_profiles,
        "comparison_table": _build_comparison_table(normalized_profiles),
        "narrative_summary": narrative_summary,
        "warnings": warnings,
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
        print(f"Warning: compare breakdown generation failed for paper {paper.id}: {error}")
        return _normalize_breakdown({}), [
            "Structured breakdown could not be generated automatically; missing fields were left as abstentions."
        ]

    normalized_breakdown = _normalize_breakdown(breakdown)
    paper.structured_breakdown = normalized_breakdown
    db.commit()

    return normalized_breakdown, []


def normalize_paper_for_compare(
    paper: Paper,
    breakdown: dict,
    sections: list[PaperSection],
    seed_warnings: list[str] | None = None,
) -> dict:
    compare_details: dict = {}
    profile_warnings = list(seed_warnings or [])

    try:
        compare_details = extract_compare_profile_details(
            title=paper.title,
            abstract=paper.abstract or "",
            breakdown=breakdown,
            sections=sections,
        )
    except Exception as error:
        print(f"Warning: compare profile extraction failed for paper {paper.id}: {error}")
        profile_warnings.append(
            "Compare profile extraction fell back to stored paper analysis because model extraction failed."
        )
        compare_details = {
            "evidence_notes": _build_fallback_evidence_notes(sections),
            "warnings": [],
        }

    profile = {
        "paper_id": str(paper.id),
        "title": paper.title,
        "authors": paper.authors or "",
        "problem": _coerce_field(
            compare_details.get("problem"),
            fallback=breakdown.get("problem"),
        ),
        "method": _coerce_field(
            compare_details.get("method"),
            fallback=breakdown.get("method"),
        ),
        "dataset_or_eval_setup": _coerce_field(
            compare_details.get("dataset_or_eval_setup")
        ),
        "key_results": _coerce_field(
            compare_details.get("key_results"),
            fallback=breakdown.get("results"),
        ),
        "strengths": _coerce_field(
            compare_details.get("strengths"),
            fallback=breakdown.get("key_contributions"),
        ),
        "weaknesses": _coerce_field(
            compare_details.get("weaknesses"),
            fallback=breakdown.get("limitations"),
        ),
        "evidence_notes": _normalize_evidence_notes_by_field(
            compare_details.get("evidence_notes"),
            sections,
        ),
        "warnings": _dedupe_strings(
            profile_warnings + _normalize_warnings(compare_details.get("warnings"))
        ),
    }

    for field in COMPARE_FIELDS:
        if profile[field] == NOT_EXPLICITLY_DISCUSSED:
            profile["warnings"].append(
                f"{COMPARE_FIELD_LABELS[field]} was not explicitly discussed in the paper."
            )

    profile["warnings"] = _dedupe_strings(profile["warnings"])
    return profile


def extract_compare_profile_details(
    title: str,
    abstract: str,
    breakdown: dict,
    sections: list[PaperSection],
) -> dict:
    section_context = _build_section_context(sections)
    breakdown_json = json.dumps(breakdown, ensure_ascii=True)

    return _request_structured_json(
        model=settings.compare_profile_model,
        schema_name="compare_profile",
        schema=COMPARE_PROFILE_JSON_SCHEMA,
        messages=[
            {
                "role": "system",
                "content": (
                    "You normalize research papers into a stable comparison profile. "
                    "Use only the provided paper content. Do not hallucinate or infer details "
                    "that are not explicitly supported by the text.\n\n"
                    "Return a JSON object with these exact keys:\n"
                    '- "problem": concise summary of the paper problem.\n'
                    '- "method": concise summary of the approach or method.\n'
                    '- "dataset_or_eval_setup": what datasets, benchmarks, tasks, or evaluation setup are used.\n'
                    '- "key_results": the most important reported results.\n'
                    '- "strengths": practical or scientific strengths supported by the paper.\n'
                    '- "weaknesses": limitations, caveats, or weak spots supported by the paper.\n'
                    '- "evidence_notes": object keyed by compare field with arrays of short section-title-only notes, '
                    'e.g. {"method": ["Method", "Implementation Details"]}.\n'
                    '- "warnings": array of short strings for missing, ambiguous, or low-confidence fields.\n\n'
                    f'If a field is not stated clearly, use "{NOT_EXPLICITLY_DISCUSSED}".'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Title: {title}\n\n"
                    f"Abstract: {abstract}\n\n"
                    f"Structured breakdown: {breakdown_json}\n\n"
                    f"Relevant sections:\n\n{section_context}"
                ),
            },
        ],
    )


def generate_comparison_synthesis(normalized_profiles: list[dict]) -> dict:
    profiles_json = json.dumps(normalized_profiles, ensure_ascii=True)

    return _request_structured_json(
        model=settings.compare_synthesis_model,
        schema_name="compare_synthesis",
        schema=COMPARE_SYNTHESIS_JSON_SCHEMA,
        messages=[
            {
                "role": "system",
                "content": (
                    "You synthesize a cross-paper comparison from normalized paper profiles. "
                    "Use only the provided profiles, including their evidence notes and warnings. "
                    "Do not invent details or collapse genuine uncertainty.\n\n"
                    "Return a JSON object with these exact keys:\n"
                    '- "problem_landscape": what the papers are trying to solve together.\n'
                    '- "method_divergence": where the methods meaningfully differ.\n'
                    '- "evaluation_differences": how datasets, benchmarks, or evaluation setups differ.\n'
                    '- "researcher_tradeoffs": the key strengths, weaknesses, and tradeoffs a researcher should care about.\n'
                    '- "warnings": array of short strings for low-evidence or difficult comparisons.\n\n'
                    "Mention paper titles when needed to keep the summary concrete. "
                    f'If a section cannot be supported, use "{NOT_EXPLICITLY_DISCUSSED_ACROSS_PAPERS}".'
                ),
            },
            {
                "role": "user",
                "content": f"Normalized compare profiles:\n\n{profiles_json}",
            },
        ],
    )


def build_comparison_narrative(
    normalized_profiles: list[dict],
) -> tuple[str, list[str]]:
    if not normalized_profiles:
        return "", []

    try:
        synthesis = _normalize_compare_synthesis(
            generate_comparison_synthesis(normalized_profiles)
        )
        return _format_narrative_summary(synthesis), synthesis["warnings"]
    except Exception as error:
        print(f"Warning: compare synthesis failed: {error}")
        return _build_fallback_narrative_summary(normalized_profiles), [
            "Cross-paper narrative summary used deterministic fallback because model synthesis failed."
        ]


def _request_structured_json(
    model: str,
    schema_name: str,
    schema: dict,
    messages: list[dict[str, str]],
) -> dict:
    return get_structured_client().generate_structured(
        messages=messages,
        model=model,
        temperature=0.2,
        schema_name=schema_name,
        schema=schema,
    )


def validate_compare_paper_ids(paper_ids: list[str]) -> list[uuid.UUID]:
    if len(paper_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="Select at least 2 papers to compare.",
        )
    if len(paper_ids) > 5:
        raise HTTPException(
            status_code=400,
            detail="You can compare up to 5 papers at a time.",
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


def load_papers_for_user(
    db: Session,
    user_id: uuid.UUID,
    paper_ids: list[uuid.UUID],
) -> list[Paper]:
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


def _load_sections_for_paper(db: Session, paper_id: uuid.UUID) -> list[PaperSection]:
    return (
        db.query(PaperSection)
        .filter(PaperSection.paper_id == paper_id)
        .order_by(PaperSection.section_order)
        .all()
    )


def _normalize_breakdown(breakdown: dict | None) -> dict:
    normalized = dict(breakdown or {})
    for field in BREAKDOWN_FIELDS.values():
        normalized[field] = _coerce_field(normalized.get(field))
    return normalized


def _coerce_field(value: object, fallback: object | None = None) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return NOT_EXPLICITLY_DISCUSSED


def _coerce_summary_field(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return NOT_EXPLICITLY_DISCUSSED_ACROSS_PAPERS


def _normalize_warnings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return _dedupe_strings(
        [str(item).strip() for item in value if str(item).strip()]
    )


def _normalize_evidence_notes_by_field(
    value: object,
    sections: list[PaperSection],
) -> dict[str, list[str]]:
    normalized = {field: [] for field in COMPARE_FIELDS}

    if isinstance(value, dict):
        for field in COMPARE_FIELDS:
            normalized[field] = _normalize_string_list(value.get(field))
        if any(normalized[field] for field in COMPARE_FIELDS):
            return normalized

    if isinstance(value, list):
        normalized = _parse_legacy_evidence_notes(value)
        if any(normalized[field] for field in COMPARE_FIELDS):
            return normalized

    return _build_fallback_evidence_notes(sections)


def _normalize_compare_synthesis(value: object) -> dict:
    synthesis = value if isinstance(value, dict) else {}
    normalized = {
        field: _coerce_summary_field(synthesis.get(field))
        for field in SUMMARY_FIELDS
    }
    warnings = _normalize_warnings(synthesis.get("warnings"))

    for field in SUMMARY_FIELDS:
        if normalized[field] == NOT_EXPLICITLY_DISCUSSED_ACROSS_PAPERS:
            warnings.append(
                f"{SUMMARY_FIELD_LABELS[field]} had insufficient explicit cross-paper evidence."
            )

    normalized["warnings"] = _dedupe_strings(warnings)
    return normalized


def _build_section_context(sections: list[PaperSection]) -> str:
    selected_sections = _select_relevant_sections(sections)
    context_parts = []
    remaining_chars = MAX_COMPARE_SECTION_CHARS

    for section in selected_sections:
        section_text = f"## {section.section_title}\n{section.content.strip()}\n\n"
        if remaining_chars <= 0:
            break
        if len(section_text) > remaining_chars:
            context_parts.append(section_text[:remaining_chars])
            break
        context_parts.append(section_text)
        remaining_chars -= len(section_text)

    return "".join(context_parts)


def _select_relevant_sections(sections: list[PaperSection]) -> list[PaperSection]:
    if not sections:
        return []

    selected_indices: list[int] = []
    seen_indices: set[int] = set()

    for index, section in enumerate(sections):
        title = section.section_title.lower()
        if section.section_order <= 2 or any(keyword in title for keyword in SECTION_KEYWORDS):
            if index not in seen_indices:
                selected_indices.append(index)
                seen_indices.add(index)

    if not selected_indices:
        selected_indices = list(range(min(len(sections), 6)))

    return [sections[index] for index in selected_indices]


def _build_comparison_table(normalized_profiles: list[dict]) -> dict:
    return {
        "columns": [
            {"key": "dimension", "label": "Dimension"},
            *[
                {"key": profile["paper_id"], "label": profile["title"]}
                for profile in normalized_profiles
            ],
        ],
        "rows": [
            {
                "key": field,
                "label": COMPARE_FIELD_LABELS[field],
                "values": [profile[field] for profile in normalized_profiles],
            }
            for field in COMPARE_FIELDS
        ],
    }


def _format_narrative_summary(synthesis: dict) -> str:
    return "\n\n".join(
        f"{SUMMARY_FIELD_LABELS[field]}: {synthesis[field]}"
        for field in SUMMARY_FIELDS
    )


def _build_fallback_narrative_summary(normalized_profiles: list[dict]) -> str:
    return "\n\n".join([
        (
            f"{SUMMARY_FIELD_LABELS['problem_landscape']}: "
            f"{_build_field_snapshot(normalized_profiles, 'problem', max_chars=220)}"
        ),
        (
            f"{SUMMARY_FIELD_LABELS['method_divergence']}: "
            f"{_build_field_snapshot(normalized_profiles, 'method', max_chars=220)}"
        ),
        (
            f"{SUMMARY_FIELD_LABELS['evaluation_differences']}: "
            f"{_build_field_snapshot(normalized_profiles, 'dataset_or_eval_setup', max_chars=220)}"
        ),
        (
            f"{SUMMARY_FIELD_LABELS['researcher_tradeoffs']}: "
            f"{_build_tradeoff_snapshot(normalized_profiles)}"
        ),
    ])


def _build_field_snapshot(
    normalized_profiles: list[dict],
    field: str,
    max_chars: int,
) -> str:
    explicit_entries = []
    missing_titles = []

    for profile in normalized_profiles:
        value = profile.get(field)
        if value == NOT_EXPLICITLY_DISCUSSED:
            missing_titles.append(profile["title"])
            continue
        explicit_entries.append(
            f"{profile['title']}: {_clip_text(str(value), max_chars)}"
        )

    if not explicit_entries:
        return NOT_EXPLICITLY_DISCUSSED_ACROSS_PAPERS

    snapshot = "; ".join(explicit_entries)
    if missing_titles:
        snapshot += f" Missing explicit detail for: {', '.join(missing_titles)}."

    return snapshot


def _build_tradeoff_snapshot(normalized_profiles: list[dict]) -> str:
    tradeoff_entries = []

    for profile in normalized_profiles:
        strengths = profile.get("strengths", NOT_EXPLICITLY_DISCUSSED)
        weaknesses = profile.get("weaknesses", NOT_EXPLICITLY_DISCUSSED)

        if (
            strengths == NOT_EXPLICITLY_DISCUSSED
            and weaknesses == NOT_EXPLICITLY_DISCUSSED
        ):
            continue

        tradeoff_entries.append(
            (
                f"{profile['title']}: strengths - {_clip_text(str(strengths), 140)}; "
                f"weaknesses - {_clip_text(str(weaknesses), 140)}"
            )
        )

    if not tradeoff_entries:
        return NOT_EXPLICITLY_DISCUSSED_ACROSS_PAPERS

    return "; ".join(tradeoff_entries)


def _collect_top_level_warnings(normalized_profiles: list[dict]) -> list[str]:
    warnings = []
    for profile in normalized_profiles:
        for warning in profile["warnings"]:
            warnings.append(f"{profile['title']}: {warning}")
    return _dedupe_strings(warnings)

def _dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    deduped = []

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)

    return deduped


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return _dedupe_strings(
        [str(item).strip() for item in value if str(item).strip()]
    )


def _parse_legacy_evidence_notes(value: list[object]) -> dict[str, list[str]]:
    normalized = {field: [] for field in COMPARE_FIELDS}

    for raw_note in value:
        note = str(raw_note).strip()
        if not note:
            continue

        matched_field = None
        detail = note

        if ":" in note:
            prefix, remainder = note.split(":", 1)
            prefix = prefix.strip()
            if prefix in COMPARE_FIELDS:
                matched_field = prefix
                detail = remainder.strip()

        if matched_field:
            parts = [part.strip() for part in detail.split(",") if part.strip()]
            normalized[matched_field].extend(parts or [detail])

    for field in COMPARE_FIELDS:
        normalized[field] = _dedupe_strings(normalized[field])

    return normalized


def _build_fallback_evidence_notes(sections: list[PaperSection]) -> dict[str, list[str]]:
    selected_sections = _select_relevant_sections(sections)
    normalized = {}

    for field in COMPARE_FIELDS:
        titles = []
        hints = EVIDENCE_SECTION_HINTS[field]
        for section in selected_sections:
            lower_title = section.section_title.lower()
            if any(hint in lower_title for hint in hints):
                titles.append(section.section_title)

        if not titles:
            titles = [section.section_title for section in selected_sections[:2]]

        normalized[field] = _dedupe_strings(titles)

    return normalized


def _clip_text(value: str, max_chars: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."
