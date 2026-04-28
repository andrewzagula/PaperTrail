import ast
import json
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.llm import get_structured_client
from app.models.models import Paper, PaperSection
from app.services.analyzer import analyze_paper
from app.workflows.implementation_graph import (
    ImplementationGraphNodes,
    ImplementationGraphState,
    build_implementation_graph,
)

NOT_EXPLICITLY_DISCLOSED = "Not explicitly discussed in the provided paper context."
IMPLEMENTATION_SAVE_DEFERRED_DETAIL = (
    "Implementation persistence will be enabled in Phase 9E."
)
IMPLEMENTATION_EXTRACTION_FALLBACK_WARNING = (
    "Algorithm extraction used deterministic fallback because model extraction failed."
)
IMPLEMENTATION_GAP_ANALYSIS_FALLBACK_WARNING = (
    "Gap analysis used deterministic fallback because model analysis failed."
)
IMPLEMENTATION_PSEUDOCODE_FALLBACK_WARNING = (
    "Pseudocode generation used deterministic fallback because model generation failed."
)
IMPLEMENTATION_CODE_FALLBACK_WARNING = (
    "Starter code generation used deterministic fallback because model generation failed."
)
IMPLEMENTATION_CODE_NORMALIZATION_FALLBACK_WARNING = (
    "Starter code generation returned no usable files; deterministic fallback files were used."
)
IMPLEMENTATION_CODE_FRAMEWORK_FALLBACK_WARNING = (
    "Starter code generation did not match the selected target framework; deterministic fallback files were used."
)
IMPLEMENTATION_REVIEW_FALLBACK_WARNING = (
    "Starter code review used deterministic fallback because model review failed."
)
IMPLEMENTATION_BREAKDOWN_FALLBACK_WARNING = (
    "Structured breakdown could not be generated automatically; algorithm extraction used available metadata and sections."
)
SPARSE_METHOD_CONTEXT_WARNING = (
    "Implementation context has sparse method detail; extracted steps may be incomplete."
)
NO_PARSED_SECTIONS_WARNING = (
    "No parsed paper sections are available for implementation context."
)
INSUFFICIENT_ALGORITHM_STEPS_WARNING = (
    "Algorithm extraction returned fewer than 2 usable steps."
)
NO_ALGORITHM_STEPS_WARNING = (
    "No grounded algorithm steps could be extracted from the available paper context."
)
MAX_IMPLEMENTATION_FOCUS_CHARS = 1000
MAX_SOURCE_SECTIONS = 8
MAX_SECTION_PREVIEW_CHARS = 1200
MAX_IMPLEMENTATION_CONTEXT_CHARS = 60000
MAX_SECTION_CONTENT_CHARS = 8000
MAX_STARTER_CODE_FILES = 4
MIN_STARTER_CODE_FILES = 2
MAX_STARTER_FILE_CHARS = 12000
MAX_STARTER_CODE_TOTAL_CHARS = 30000
MIN_USABLE_ALGORITHM_STEPS = 2
SUPPORTED_TARGET_LANGUAGES = ("python",)
SUPPORTED_TARGET_FRAMEWORKS = ("pytorch", "generic-python")
SUPPORTED_STARTER_EXTENSIONS = (".py", ".md")
GAP_CATEGORIES = (
    "equations",
    "data",
    "model_architecture",
    "hyperparameters",
    "evaluation",
    "environment_dependencies",
)
GAP_SEVERITIES = ("low", "medium", "high")

BREAKDOWN_FIELDS = (
    "problem",
    "method",
    "key_contributions",
    "results",
    "limitations",
    "future_work",
)

IMPLEMENTATION_SECTION_KEYWORDS = (
    "abstract",
    "method",
    "methods",
    "model",
    "architecture",
    "algorithm",
    "approach",
    "experiment",
    "experiments",
    "evaluation",
    "appendix",
    "limitation",
    "limitations",
)

METHOD_SECTION_KEYWORDS = (
    "method",
    "methods",
    "model",
    "architecture",
    "algorithm",
    "approach",
    "implementation",
    "training",
    "inference",
    "optimization",
)

IMPLEMENTATION_ALGORITHM_STEP_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "order": {"type": "integer"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "inputs": {"type": "array", "items": {"type": "string"}},
        "outputs": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "order",
        "title",
        "description",
        "inputs",
        "outputs",
        "evidence",
        "warnings",
    ],
}

IMPLEMENTATION_ALGORITHM_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "implementation_summary": {"type": "string"},
        "algorithm_steps": {
            "type": "array",
            "items": IMPLEMENTATION_ALGORITHM_STEP_JSON_SCHEMA,
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["implementation_summary", "algorithm_steps", "warnings"],
}

IMPLEMENTATION_GAP_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "category": {"type": "string", "enum": list(GAP_CATEGORIES)},
        "description": {"type": "string"},
        "severity": {"type": "string", "enum": list(GAP_SEVERITIES)},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "description", "severity", "evidence"],
}

IMPLEMENTATION_GAPS_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "assumptions_and_gaps": {
            "type": "array",
            "items": IMPLEMENTATION_GAP_JSON_SCHEMA,
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["assumptions_and_gaps", "warnings"],
}

IMPLEMENTATION_PSEUDOCODE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "setup": {"type": "string"},
        "model": {"type": "string"},
        "training_or_inference": {"type": "string"},
        "evaluation": {"type": "string"},
        "extension_points": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "setup",
        "model",
        "training_or_inference",
        "evaluation",
        "extension_points",
        "warnings",
    ],
}

IMPLEMENTATION_STARTER_CODE_FILE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "path": {"type": "string"},
        "language": {"type": "string"},
        "purpose": {"type": "string"},
        "content": {"type": "string"},
    },
    "required": ["path", "language", "purpose", "content"],
}

IMPLEMENTATION_CODE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "starter_code": {
            "type": "array",
            "items": IMPLEMENTATION_STARTER_CODE_FILE_JSON_SCHEMA,
        },
        "setup_notes": {"type": "array", "items": {"type": "string"}},
        "test_plan": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["starter_code", "setup_notes", "test_plan", "warnings"],
}

IMPLEMENTATION_REVIEW_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["warnings"],
}


def generate_paper_implementation(
    db: Session,
    user_id: uuid.UUID,
    paper_id: str,
    focus: str | None = None,
    target_language: str = "python",
    target_framework: str = "pytorch",
) -> dict:
    normalized_paper_id = validate_implementation_paper_id(paper_id)
    normalized_focus = normalize_implementation_focus(focus)
    normalized_language = validate_target_language(target_language)
    normalized_framework = validate_target_framework(target_framework)

    graph = build_implementation_graph(
        ImplementationGraphNodes(
            load_paper=_implementation_graph_load_paper,
            prepare_context=_implementation_graph_prepare_context,
            extract_algorithm=_implementation_graph_extract_algorithm,
            analyze_gaps=_implementation_graph_analyze_gaps,
            generate_pseudocode=_implementation_graph_generate_pseudocode,
            generate_starter_code=_implementation_graph_generate_starter_code,
            review_scaffold=_implementation_graph_review_scaffold,
            build_response=_implementation_graph_build_response,
        )
    )
    result = graph.invoke({
        "db": db,
        "user_id": user_id,
        "paper_id": normalized_paper_id,
        "focus": normalized_focus,
        "target_language": normalized_language,
        "target_framework": normalized_framework,
    })

    return {
        "paper": result["paper"],
        "source_sections": result["source_sections"],
        "implementation_summary": result["implementation_summary"],
        "algorithm_steps": result["algorithm_steps"],
        "assumptions_and_gaps": result["assumptions_and_gaps"],
        "pseudocode": result["pseudocode"],
        "starter_code": result["starter_code"],
        "setup_notes": result["setup_notes"],
        "test_plan": result["test_plan"],
        "warnings": result["warnings"],
    }


def validate_implementation_paper_id(paper_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(paper_id).strip())
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid paper ID: {paper_id}")


def normalize_implementation_focus(focus: str | None) -> str | None:
    if focus is None:
        return None

    normalized_focus = focus.strip()
    if len(normalized_focus) > MAX_IMPLEMENTATION_FOCUS_CHARS:
        raise HTTPException(
            status_code=400,
            detail="Implementation focus must be 1000 characters or fewer.",
        )

    return normalized_focus or None


def validate_target_language(target_language: str) -> str:
    normalized_language = str(target_language).strip()
    if normalized_language not in SUPPORTED_TARGET_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported target language. Supported values: python.",
        )

    return normalized_language


def validate_target_framework(target_framework: str) -> str:
    normalized_framework = str(target_framework).strip()
    if normalized_framework not in SUPPORTED_TARGET_FRAMEWORKS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported target framework. Supported values: "
                "pytorch, generic-python."
            ),
        )

    return normalized_framework


def load_implementation_paper_for_user(
    db: Session,
    user_id: uuid.UUID,
    paper_id: uuid.UUID,
) -> Paper:
    paper = (
        db.query(Paper)
        .filter(Paper.user_id == user_id, Paper.id == paper_id)
        .first()
    )
    if not paper:
        raise HTTPException(
            status_code=404,
            detail=f"Paper not found in your library: {paper_id}",
        )

    return paper


def _implementation_graph_load_paper(
    state: ImplementationGraphState,
) -> ImplementationGraphState:
    return {
        "paper": load_implementation_paper_for_user(
            state["db"],
            state["user_id"],
            state["paper_id"],
        )
    }


def _implementation_graph_prepare_context(
    state: ImplementationGraphState,
) -> ImplementationGraphState:
    db = state["db"]
    paper = state["paper"]
    sections = _load_sections_for_paper(db, paper.id)
    selected_sections = _select_implementation_sections(sections)
    source_sections = [
        _serialize_source_section(section)
        for section in selected_sections[:MAX_SOURCE_SECTIONS]
    ]
    breakdown, breakdown_warnings = ensure_structured_breakdown(db, paper, sections)

    warnings = list(state.get("warnings") or [])
    warnings.extend(breakdown_warnings)
    if not sections:
        warnings.append(NO_PARSED_SECTIONS_WARNING)
    if _has_sparse_method_context(selected_sections, breakdown):
        warnings.append(SPARSE_METHOD_CONTEXT_WARNING)

    return {
        "sections": sections,
        "source_sections": source_sections,
        "breakdown": breakdown,
        "implementation_context": _build_implementation_context(
            paper=paper,
            breakdown=breakdown,
            selected_sections=selected_sections,
        ),
        "warnings": _dedupe_strings(warnings),
    }


def _implementation_graph_extract_algorithm(
    state: ImplementationGraphState,
) -> ImplementationGraphState:
    implementation_context = state["implementation_context"]
    warnings = list(state.get("warnings") or [])
    summary = _build_fallback_implementation_summary(
        state["paper"],
        implementation_context,
    )
    algorithm_steps: list[dict[str, Any]] = []

    if _can_extract_algorithm_steps(implementation_context):
        try:
            payload = extract_algorithm_details(
                implementation_context=implementation_context,
                focus=state.get("focus"),
                target_framework=state["target_framework"],
            )
            algorithm_steps, normalization_warnings = _normalize_algorithm_steps(
                payload.get("algorithm_steps"),
                implementation_context,
            )
            summary = _coerce_text(
                payload.get("implementation_summary"),
                summary,
            )
            warnings.extend(_normalize_string_list(payload.get("warnings")))
            warnings.extend(normalization_warnings)
            if len(algorithm_steps) < MIN_USABLE_ALGORITHM_STEPS:
                fallback_steps = _build_deterministic_algorithm_steps(
                    implementation_context
                )
                if len(fallback_steps) > len(algorithm_steps):
                    algorithm_steps = fallback_steps
                    summary = _build_fallback_implementation_summary(
                        state["paper"],
                        implementation_context,
                    )
                warnings.append(INSUFFICIENT_ALGORITHM_STEPS_WARNING)
        except Exception:
            algorithm_steps = _build_deterministic_algorithm_steps(
                implementation_context
            )
            warnings.append(IMPLEMENTATION_EXTRACTION_FALLBACK_WARNING)
    else:
        warnings.append(NO_ALGORITHM_STEPS_WARNING)

    if not algorithm_steps:
        warnings.append(NO_ALGORITHM_STEPS_WARNING)
    elif len(algorithm_steps) < MIN_USABLE_ALGORITHM_STEPS:
        warnings.append(INSUFFICIENT_ALGORITHM_STEPS_WARNING)

    return {
        "implementation_summary": _add_focus_to_summary(
            summary,
            state.get("focus"),
        ),
        "algorithm_steps": algorithm_steps,
        "warnings": _dedupe_strings(warnings),
    }


def _implementation_graph_analyze_gaps(
    state: ImplementationGraphState,
) -> ImplementationGraphState:
    implementation_context = state.get("implementation_context") or {}
    algorithm_steps = state.get("algorithm_steps") or []
    warnings = list(state.get("warnings") or [])
    fallback_gaps = _build_deterministic_assumptions_and_gaps(
        implementation_context=implementation_context,
        algorithm_steps=algorithm_steps,
        warnings=warnings,
    )

    if not algorithm_steps:
        return {"assumptions_and_gaps": fallback_gaps}

    try:
        payload = analyze_implementation_gaps(
            implementation_context=implementation_context,
            algorithm_steps=algorithm_steps,
            warnings=warnings,
            focus=state.get("focus"),
            target_framework=state["target_framework"],
        )
        assumptions_and_gaps, normalization_warnings = _normalize_assumptions_and_gaps(
            payload.get("assumptions_and_gaps"),
            implementation_context,
        )
        warnings.extend(_normalize_string_list(payload.get("warnings")))
        warnings.extend(normalization_warnings)
        if not assumptions_and_gaps:
            assumptions_and_gaps = fallback_gaps
    except Exception:
        assumptions_and_gaps = fallback_gaps
        warnings.append(IMPLEMENTATION_GAP_ANALYSIS_FALLBACK_WARNING)

    return {
        "assumptions_and_gaps": assumptions_and_gaps,
        "warnings": _dedupe_strings(warnings),
    }


def _implementation_graph_generate_pseudocode(
    state: ImplementationGraphState,
) -> ImplementationGraphState:
    implementation_context = state.get("implementation_context") or {}
    algorithm_steps = state.get("algorithm_steps") or []
    assumptions_and_gaps = state.get("assumptions_and_gaps") or []
    warnings = list(state.get("warnings") or [])

    if not algorithm_steps:
        return {
            "pseudocode": _build_deterministic_pseudocode(
                implementation_context=implementation_context,
                algorithm_steps=algorithm_steps,
                assumptions_and_gaps=assumptions_and_gaps,
                focus=state.get("focus"),
                target_framework=state["target_framework"],
            )
        }

    try:
        payload = generate_implementation_pseudocode(
            implementation_context=implementation_context,
            algorithm_steps=algorithm_steps,
            assumptions_and_gaps=assumptions_and_gaps,
            focus=state.get("focus"),
            target_framework=state["target_framework"],
        )
        pseudocode = _normalize_pseudocode_payload(
            payload,
            implementation_context=implementation_context,
            algorithm_steps=algorithm_steps,
            assumptions_and_gaps=assumptions_and_gaps,
            focus=state.get("focus"),
            target_framework=state["target_framework"],
        )
        warnings.extend(_normalize_string_list(payload.get("warnings")))
    except Exception:
        pseudocode = _build_deterministic_pseudocode(
            implementation_context=implementation_context,
            algorithm_steps=algorithm_steps,
            assumptions_and_gaps=assumptions_and_gaps,
            focus=state.get("focus"),
            target_framework=state["target_framework"],
        )
        warnings.append(IMPLEMENTATION_PSEUDOCODE_FALLBACK_WARNING)

    return {
        "pseudocode": pseudocode,
        "warnings": _dedupe_strings(warnings),
    }


def _implementation_graph_generate_starter_code(
    state: ImplementationGraphState,
) -> ImplementationGraphState:
    implementation_context = state.get("implementation_context") or {}
    algorithm_steps = state.get("algorithm_steps") or []
    assumptions_and_gaps = state.get("assumptions_and_gaps") or []
    pseudocode = state.get("pseudocode") or ""
    warnings = list(state.get("warnings") or [])

    fallback_payload = _build_deterministic_starter_code_payload(
        implementation_context=implementation_context,
        algorithm_steps=algorithm_steps,
        assumptions_and_gaps=assumptions_and_gaps,
        pseudocode=pseudocode,
        focus=state.get("focus"),
        target_framework=state["target_framework"],
    )

    if not algorithm_steps:
        return {
            **fallback_payload,
            "warnings": _dedupe_strings([
                *warnings,
                NO_ALGORITHM_STEPS_WARNING,
            ]),
        }

    try:
        payload = generate_implementation_starter_code(
            implementation_context=implementation_context,
            algorithm_steps=algorithm_steps,
            assumptions_and_gaps=assumptions_and_gaps,
            pseudocode=pseudocode,
            focus=state.get("focus"),
            target_language=state["target_language"],
            target_framework=state["target_framework"],
        )
        starter_code, normalization_warnings = _normalize_starter_code_files(
            payload.get("starter_code"),
            fallback_payload["starter_code"],
            assumptions_and_gaps,
            target_framework=state["target_framework"],
        )
        if not starter_code:
            starter_code = fallback_payload["starter_code"]
            normalization_warnings.append(
                IMPLEMENTATION_CODE_NORMALIZATION_FALLBACK_WARNING
            )
        setup_notes = _normalize_string_list(payload.get("setup_notes")) or fallback_payload[
            "setup_notes"
        ]
        test_plan = _normalize_string_list(payload.get("test_plan")) or fallback_payload[
            "test_plan"
        ]
        if _starter_payload_conflicts_with_target_framework(
            starter_code,
            setup_notes,
            test_plan,
            state["target_framework"],
        ):
            starter_code = fallback_payload["starter_code"]
            setup_notes = fallback_payload["setup_notes"]
            test_plan = fallback_payload["test_plan"]
            normalization_warnings.append(IMPLEMENTATION_CODE_FRAMEWORK_FALLBACK_WARNING)
        warnings.extend(_normalize_string_list(payload.get("warnings")))
        warnings.extend(normalization_warnings)
    except Exception:
        starter_code = fallback_payload["starter_code"]
        setup_notes = fallback_payload["setup_notes"]
        test_plan = fallback_payload["test_plan"]
        warnings.append(IMPLEMENTATION_CODE_FALLBACK_WARNING)

    return {
        "starter_code": starter_code,
        "setup_notes": setup_notes,
        "test_plan": test_plan,
        "warnings": _dedupe_strings(warnings),
    }


def _implementation_graph_review_scaffold(
    state: ImplementationGraphState,
) -> ImplementationGraphState:
    warnings = list(state.get("warnings") or [])
    algorithm_steps = state.get("algorithm_steps") or []
    starter_code = state.get("starter_code") or []

    if not algorithm_steps:
        warnings.append(NO_ALGORITHM_STEPS_WARNING)
    elif len(algorithm_steps) < MIN_USABLE_ALGORITHM_STEPS:
        warnings.append(INSUFFICIENT_ALGORITHM_STEPS_WARNING)

    if starter_code and algorithm_steps:
        try:
            payload = review_implementation_scaffold(
                implementation_context=state.get("implementation_context") or {},
                algorithm_steps=algorithm_steps,
                assumptions_and_gaps=state.get("assumptions_and_gaps") or [],
                pseudocode=state.get("pseudocode") or "",
                starter_code=starter_code,
                focus=state.get("focus"),
                target_framework=state["target_framework"],
            )
            warnings.extend(_normalize_string_list(payload.get("warnings")))
        except Exception:
            warnings.append(IMPLEMENTATION_REVIEW_FALLBACK_WARNING)

    reviewed_code, review_warnings = _review_starter_code_deterministically(
        starter_code,
        state.get("assumptions_and_gaps") or [],
    )
    warnings.extend(review_warnings)

    return {
        "starter_code": reviewed_code,
        "warnings": _dedupe_strings(warnings),
    }


def _implementation_graph_build_response(
    state: ImplementationGraphState,
) -> ImplementationGraphState:
    paper = state["paper"]
    target_framework = state["target_framework"]

    return {
        "paper": _serialize_implementation_paper(paper),
        "implementation_summary": state.get("implementation_summary")
        or _build_fallback_implementation_summary(
            paper,
            state.get("implementation_context") or {},
        ),
        "algorithm_steps": state.get("algorithm_steps") or [],
        "assumptions_and_gaps": state.get("assumptions_and_gaps") or [],
        "pseudocode": state.get("pseudocode") or "",
        "starter_code": state.get("starter_code") or [],
        "setup_notes": state.get("setup_notes")
        or [
            (
                "Phase 9C generates grounded gaps and pseudocode; "
                f"Phase 9D adds bounded {target_framework} starter code scaffolds."
            )
        ],
        "test_plan": state.get("test_plan")
        or [
            (
                "Use the extracted steps as an implementation checklist and verify each "
                "TODO against the original paper before coding."
            )
        ],
        "warnings": _dedupe_strings(state.get("warnings") or []),
    }


def ensure_structured_breakdown(
    db: Session,
    paper: Paper,
    sections: list[PaperSection],
) -> tuple[dict[str, str], list[str]]:
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
    except Exception:
        return _normalize_breakdown({}), [IMPLEMENTATION_BREAKDOWN_FALLBACK_WARNING]

    normalized_breakdown = _normalize_breakdown(breakdown)
    paper.structured_breakdown = normalized_breakdown
    db.commit()

    return normalized_breakdown, []


def extract_algorithm_details(
    implementation_context: dict[str, Any],
    focus: str | None,
    target_framework: str,
) -> dict:
    context_json = json.dumps(implementation_context, ensure_ascii=True)
    focus_text = focus or "No user focus provided."

    return get_structured_client().generate_structured(
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract implementation-relevant algorithm steps from a single "
                    "research paper. Use only the provided paper context. Do not invent "
                    "equations, hyperparameters, datasets, architecture details, or "
                    "training procedures. If a detail is missing, mention that in warnings.\n\n"
                    "Return JSON with an implementation_summary, ordered algorithm_steps, "
                    "and warnings. Each step must be grounded in evidence from the provided "
                    "section titles or structured breakdown. Fold objective/loss details, "
                    "model components, and data assumptions into the step description, "
                    "inputs, outputs, or warnings. The user focus is only a lens for "
                    "prioritization; it is not permission to ignore grounding."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target framework: {target_framework}\n"
                    f"User focus: {focus_text}\n\n"
                    f"Implementation context:\n\n{context_json}"
                ),
            },
        ],
        model=settings.implementation_extraction_model,
        temperature=0.2,
        schema_name="implementation_algorithm",
        schema=IMPLEMENTATION_ALGORITHM_JSON_SCHEMA,
    )


def analyze_implementation_gaps(
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    warnings: list[str],
    focus: str | None,
    target_framework: str,
) -> dict:
    context_json = json.dumps(implementation_context, ensure_ascii=True)
    steps_json = json.dumps(algorithm_steps, ensure_ascii=True)
    warnings_json = json.dumps(warnings, ensure_ascii=True)
    focus_text = focus or "No user focus provided."

    return get_structured_client().generate_structured(
        messages=[
            {
                "role": "system",
                "content": (
                    "You identify implementation gaps in a single research paper. Use "
                    "only the provided paper context, extracted algorithm steps, and "
                    "existing warnings. Do not invent missing details. Classify every "
                    "major missing implementation detail into exactly one of these "
                    "categories: equations, data, model_architecture, hyperparameters, "
                    "evaluation, environment_dependencies.\n\n"
                    "Return JSON with assumptions_and_gaps and warnings. Each gap must "
                    "have category, description, severity, and evidence. Evidence must "
                    "name source sections, structured breakdown fields, algorithm steps, "
                    "or existing warnings. The user focus is only a prioritization lens; "
                    "it is not permission to ignore source grounding."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target framework: {target_framework}\n"
                    f"User focus: {focus_text}\n\n"
                    f"Implementation context:\n\n{context_json}\n\n"
                    f"Algorithm steps:\n\n{steps_json}\n\n"
                    f"Existing warnings:\n\n{warnings_json}"
                ),
            },
        ],
        model=settings.implementation_extraction_model,
        temperature=0.2,
        schema_name="implementation_gaps",
        schema=IMPLEMENTATION_GAPS_JSON_SCHEMA,
    )


def generate_implementation_pseudocode(
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
    focus: str | None,
    target_framework: str,
) -> dict:
    context_json = json.dumps(implementation_context, ensure_ascii=True)
    steps_json = json.dumps(algorithm_steps, ensure_ascii=True)
    gaps_json = json.dumps(assumptions_and_gaps, ensure_ascii=True)
    focus_text = focus or "No user focus provided."

    return get_structured_client().generate_structured(
        messages=[
            {
                "role": "system",
                "content": (
                    "You write grounded implementation pseudocode for a single research "
                    "paper. Use only the provided paper context, extracted algorithm "
                    "steps, and assumptions/gaps. Do not silently fill unsupported "
                    "details. Put unsupported equations, architecture choices, data "
                    "formats, hyperparameters, evaluation details, and dependencies into "
                    "explicit TODO lines.\n\n"
                    "Return JSON sections for setup, model, training_or_inference, "
                    "evaluation, extension_points, and warnings. The pseudocode should "
                    "be Python-like, understandable without rereading the raw paper, and "
                    "bounded to starter-scaffold planning rather than runnable code. The "
                    "user focus is only a lens for emphasis."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target framework: {target_framework}\n"
                    f"User focus: {focus_text}\n\n"
                    f"Implementation context:\n\n{context_json}\n\n"
                    f"Algorithm steps:\n\n{steps_json}\n\n"
                    f"Assumptions and gaps:\n\n{gaps_json}"
                ),
            },
        ],
        model=settings.implementation_extraction_model,
        temperature=0.2,
        schema_name="implementation_pseudocode",
        schema=IMPLEMENTATION_PSEUDOCODE_JSON_SCHEMA,
    )


def generate_implementation_starter_code(
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
    pseudocode: str,
    focus: str | None,
    target_language: str,
    target_framework: str,
) -> dict:
    context_json = json.dumps(implementation_context, ensure_ascii=True)
    steps_json = json.dumps(algorithm_steps, ensure_ascii=True)
    gaps_json = json.dumps(assumptions_and_gaps, ensure_ascii=True)
    focus_text = focus or "No user focus provided."

    return get_structured_client().generate_structured(
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate starter code scaffolds for a single research paper. "
                    "Use only the provided paper context, extracted algorithm steps, "
                    "gap analysis, and pseudocode. The output is starter code, not a "
                    "verified reproduction. Return 2 to 4 small files as structured "
                    "text objects with path, language, purpose, and content. Do not "
                    "include hidden network calls, dataset downloads, API keys, provider "
                    "SDK usage, shell/process execution, eval, or exec. Do not write "
                    "files or run code. Put TODO comments anywhere the paper omits "
                    "equations, architecture details, hyperparameters, datasets, metrics, "
                    "or environment requirements."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target language: {target_language}\n"
                    f"Target framework: {target_framework}\n"
                    f"User focus: {focus_text}\n\n"
                    "Preferred files:\n"
                    "- pytorch: README.md, data.py, model.py, train.py\n"
                    "- generic-python: README.md, pipeline.py, data.py, tests_smoke.py\n\n"
                    f"Implementation context:\n\n{context_json}\n\n"
                    f"Algorithm steps:\n\n{steps_json}\n\n"
                    f"Assumptions and gaps:\n\n{gaps_json}\n\n"
                    f"Pseudocode:\n\n{pseudocode}"
                ),
            },
        ],
        model=settings.implementation_code_model,
        temperature=0.2,
        schema_name="implementation_starter_code",
        schema=IMPLEMENTATION_CODE_JSON_SCHEMA,
    )


def review_implementation_scaffold(
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
    pseudocode: str,
    starter_code: list[dict[str, Any]],
    focus: str | None,
    target_framework: str,
) -> dict:
    context_json = json.dumps(implementation_context, ensure_ascii=True)
    steps_json = json.dumps(algorithm_steps, ensure_ascii=True)
    gaps_json = json.dumps(assumptions_and_gaps, ensure_ascii=True)
    code_json = json.dumps(starter_code, ensure_ascii=True)
    focus_text = focus or "No user focus provided."

    return get_structured_client().generate_structured(
        messages=[
            {
                "role": "system",
                "content": (
                    "You review starter code generated from a single research paper. "
                    "Use only the provided context. Return warnings for unsupported "
                    "claims, missing TODOs, hidden network calls, dataset downloads, "
                    "API keys, provider SDK usage, shell/process execution, eval, exec, "
                    "or any code that appears to go beyond a bounded starter scaffold. "
                    "Do not rewrite code; only return concise warnings."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target framework: {target_framework}\n"
                    f"User focus: {focus_text}\n\n"
                    f"Implementation context:\n\n{context_json}\n\n"
                    f"Algorithm steps:\n\n{steps_json}\n\n"
                    f"Assumptions and gaps:\n\n{gaps_json}\n\n"
                    f"Pseudocode:\n\n{pseudocode}\n\n"
                    f"Starter code:\n\n{code_json}"
                ),
            },
        ],
        model=settings.implementation_review_model,
        temperature=0.1,
        schema_name="implementation_scaffold_review",
        schema=IMPLEMENTATION_REVIEW_JSON_SCHEMA,
    )


def _load_sections_for_paper(db: Session, paper_id: uuid.UUID) -> list[PaperSection]:
    return (
        db.query(PaperSection)
        .filter(PaperSection.paper_id == paper_id)
        .order_by(PaperSection.section_order)
        .all()
    )


def _select_implementation_sections(
    sections: list[PaperSection],
) -> list[PaperSection]:
    if not sections:
        return []

    selected_indices: list[int] = []
    seen_indices: set[int] = set()

    for index, section in enumerate(sections):
        title = section.section_title.lower()
        if (
            section.section_order <= 1
            or any(keyword in title for keyword in IMPLEMENTATION_SECTION_KEYWORDS)
        ) and index not in seen_indices:
            selected_indices.append(index)
            seen_indices.add(index)

    if not selected_indices:
        selected_indices = list(range(min(len(sections), MAX_SOURCE_SECTIONS)))

    return [sections[index] for index in selected_indices[:MAX_SOURCE_SECTIONS]]


def _build_implementation_context(
    paper: Paper,
    breakdown: dict[str, str],
    selected_sections: list[PaperSection],
) -> dict[str, Any]:
    remaining_chars = MAX_IMPLEMENTATION_CONTEXT_CHARS
    relevant_sections = []

    for section in selected_sections:
        if remaining_chars <= 0:
            break

        content = _clip_text(
            " ".join((section.content or "").split()),
            min(remaining_chars, MAX_SECTION_CONTENT_CHARS),
        )
        relevant_sections.append({
            "id": str(section.id),
            "title": section.section_title,
            "section_order": section.section_order,
            "content": content,
        })
        remaining_chars -= len(section.section_title) + len(content)

    return {
        "paper": {
            "id": str(paper.id),
            "title": paper.title,
            "authors": paper.authors or "",
            "abstract": paper.abstract or "",
            "arxiv_url": paper.arxiv_url or "",
        },
        "structured_breakdown": breakdown,
        "relevant_sections": relevant_sections,
    }


def _has_sparse_method_context(
    selected_sections: list[PaperSection],
    breakdown: dict[str, str],
) -> bool:
    has_method_section = any(
        _section_title_matches_method_context(section.section_title)
        for section in selected_sections
    )
    has_method_breakdown = breakdown.get("method") != NOT_EXPLICITLY_DISCLOSED
    return not has_method_section and not has_method_breakdown


def _can_extract_algorithm_steps(implementation_context: dict[str, Any]) -> bool:
    breakdown = implementation_context.get("structured_breakdown") or {}
    sections = implementation_context.get("relevant_sections") or []
    has_section_content = any(
        str(section.get("content", "")).strip()
        for section in sections
        if isinstance(section, dict)
    )
    return has_section_content or breakdown.get("method") != NOT_EXPLICITLY_DISCLOSED


def _normalize_algorithm_steps(
    value: object,
    implementation_context: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list):
        return [], []

    steps = []
    warnings = []
    fallback_evidence = _fallback_evidence(implementation_context)

    for item in value:
        if not isinstance(item, dict):
            continue

        title = _coerce_text(item.get("title"), "")
        description = _coerce_text(item.get("description"), "")
        if not title and not description:
            continue

        evidence = _normalize_string_list(item.get("evidence")) or fallback_evidence
        if not _normalize_string_list(item.get("evidence")):
            warnings.append(
                f"{title or 'Algorithm step'} had no evidence references; available source context was attached."
            )

        step_warnings = _normalize_string_list(item.get("warnings"))
        warnings.extend(
            f"{title or 'Algorithm step'}: {warning}"
            for warning in step_warnings
        )

        steps.append({
            "order": len(steps) + 1,
            "title": title or f"Algorithm step {len(steps) + 1}",
            "description": description or NOT_EXPLICITLY_DISCLOSED,
            "inputs": _normalize_string_list(item.get("inputs"))
            or [NOT_EXPLICITLY_DISCLOSED],
            "outputs": _normalize_string_list(item.get("outputs"))
            or [NOT_EXPLICITLY_DISCLOSED],
            "evidence": evidence,
        })

    return steps, _dedupe_strings(warnings)


def _normalize_assumptions_and_gaps(
    value: object,
    implementation_context: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list):
        return [], []

    gaps = []
    warnings = []
    fallback_evidence = _fallback_evidence(implementation_context)

    for item in value:
        if not isinstance(item, dict):
            continue

        description = _coerce_text(item.get("description"), "")
        if not description:
            continue

        evidence = _normalize_string_list(item.get("evidence")) or fallback_evidence
        if not _normalize_string_list(item.get("evidence")):
            warnings.append(
                f"{description} had no evidence references; available source context was attached."
            )

        gaps.append({
            "category": _normalize_gap_category(item.get("category"), description),
            "description": description,
            "severity": _normalize_gap_severity(item.get("severity"), description),
            "evidence": evidence,
        })

    return _dedupe_gaps(gaps), _dedupe_strings(warnings)


def _build_deterministic_assumptions_and_gaps(
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    fallback_evidence = _fallback_evidence(implementation_context)
    breakdown = implementation_context.get("structured_breakdown") or {}
    relevant_sections = [
        section
        for section in implementation_context.get("relevant_sections", [])
        if isinstance(section, dict)
    ]

    if not relevant_sections:
        _append_gap(
            gaps,
            "data",
            "No parsed paper sections are available, so implementation details must be recovered from metadata or the original PDF.",
            "high",
            ["Paper metadata"],
        )

    if breakdown.get("method") == NOT_EXPLICITLY_DISCLOSED:
        _append_gap(
            gaps,
            "model_architecture",
            "The structured breakdown does not explicitly describe the method or architecture.",
            "high",
            ["Structured breakdown: method"],
        )

    if breakdown.get("results") == NOT_EXPLICITLY_DISCLOSED:
        _append_gap(
            gaps,
            "evaluation",
            "The provided context does not explicitly describe expected results or evaluation targets.",
            "medium",
            ["Structured breakdown: results"],
        )

    if not algorithm_steps:
        _append_gap(
            gaps,
            "model_architecture",
            "No grounded algorithm steps were available to translate into implementation logic.",
            "high",
            fallback_evidence,
        )
    elif len(algorithm_steps) < MIN_USABLE_ALGORITHM_STEPS:
        _append_gap(
            gaps,
            "model_architecture",
            "The extracted algorithm has fewer than two usable steps, so the scaffold may miss major implementation stages.",
            "medium",
            fallback_evidence,
        )

    for warning in warnings:
        category = _classify_gap_category(warning)
        _append_gap(
            gaps,
            category,
            warning,
            _severity_from_text(warning),
            fallback_evidence,
        )

    for step in algorithm_steps:
        title = _coerce_text(step.get("title"), "Algorithm step")
        evidence = _normalize_string_list(step.get("evidence")) or fallback_evidence
        description = _coerce_text(step.get("description"), "")
        if _is_unspecified_text(description):
            _append_gap(
                gaps,
                _classify_gap_category(description),
                f"{title} contains unsupported or missing implementation detail: {description}",
                "medium",
                evidence,
            )

        for input_item in _normalize_string_list(step.get("inputs")):
            if _is_unspecified_text(input_item):
                _append_gap(
                    gaps,
                    "data",
                    f"{title} does not define required input or data details: {input_item}",
                    "medium",
                    evidence,
                )

        for output_item in _normalize_string_list(step.get("outputs")):
            if _is_unspecified_text(output_item):
                _append_gap(
                    gaps,
                    "evaluation",
                    f"{title} does not define expected outputs or success criteria: {output_item}",
                    "medium",
                    evidence,
                )

    step_text = " ".join(_step_text(step) for step in algorithm_steps).lower()
    if algorithm_steps and "train" in step_text and not _has_gap_category(
        gaps,
        "hyperparameters",
    ):
        _append_gap(
            gaps,
            "hyperparameters",
            "Training hyperparameters such as optimizer, learning rate, batch size, and stopping criteria may need confirmation from the paper or experiments.",
            "medium",
            _algorithm_step_evidence(algorithm_steps, fallback_evidence),
        )

    if algorithm_steps and (
        "objective" in step_text or "loss" in step_text or "equation" in step_text
    ) and not _has_gap_category(gaps, "equations"):
        _append_gap(
            gaps,
            "equations",
            "Exact objective, loss, or equation details should be verified before implementation.",
            "medium",
            _algorithm_step_evidence(algorithm_steps, fallback_evidence),
        )

    return _dedupe_gaps(gaps)


def _normalize_pseudocode_payload(
    payload: dict,
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
    focus: str | None,
    target_framework: str,
) -> str:
    sections = {
        "setup": _coerce_text(payload.get("setup"), ""),
        "model": _coerce_text(payload.get("model"), ""),
        "training_or_inference": _coerce_text(
            payload.get("training_or_inference"),
            "",
        ),
        "evaluation": _coerce_text(payload.get("evaluation"), ""),
        "extension_points": _coerce_text(payload.get("extension_points"), ""),
    }
    if not any(sections.values()):
        return _build_deterministic_pseudocode(
            implementation_context=implementation_context,
            algorithm_steps=algorithm_steps,
            assumptions_and_gaps=assumptions_and_gaps,
            focus=focus,
            target_framework=target_framework,
        )

    fallback_sections = _deterministic_pseudocode_sections(
        implementation_context=implementation_context,
        algorithm_steps=algorithm_steps,
        assumptions_and_gaps=assumptions_and_gaps,
        focus=focus,
        target_framework=target_framework,
    )
    for key, value in fallback_sections.items():
        if not sections[key]:
            sections[key] = value

    if assumptions_and_gaps and "todo" not in sections["extension_points"].lower():
        sections["extension_points"] = "\n".join([
            sections["extension_points"],
            *_gap_todo_lines(assumptions_and_gaps),
        ])

    return _format_pseudocode_sections(sections)


def _build_deterministic_pseudocode(
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
    focus: str | None,
    target_framework: str,
) -> str:
    return _format_pseudocode_sections(
        _deterministic_pseudocode_sections(
            implementation_context=implementation_context,
            algorithm_steps=algorithm_steps,
            assumptions_and_gaps=assumptions_and_gaps,
            focus=focus,
            target_framework=target_framework,
        )
    )


def _deterministic_pseudocode_sections(
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
    focus: str | None,
    target_framework: str,
) -> dict[str, str]:
    paper = implementation_context.get("paper") or {}
    paper_title = paper.get("title") or "the paper"
    focus_line = f"# Focus: {focus}" if focus else "# Focus: full method scaffold"
    step_lines = _algorithm_step_pseudocode_lines(algorithm_steps)
    gap_lines = _gap_todo_lines(assumptions_and_gaps)

    return {
        "setup": "\n".join([
            f"# Paper: {paper_title}",
            f"# Target framework: {target_framework}",
            focus_line,
            "source_context = load_grounded_sections()",
            "paper_inputs = prepare_inputs(source_context)",
            "# TODO: Replace placeholders with paper-specific data loading and preprocessing.",
        ]),
        "model": "\n".join([
            "model = build_model_components()",
            "# TODO: Fill architecture details only where the paper explicitly specifies them.",
            *step_lines,
        ]),
        "training_or_inference": "\n".join([
            "for batch in iterate_paper_data(paper_inputs):",
            "    outputs = model(batch)",
            "    loss_or_score = compute_paper_objective(outputs, batch)",
            "    # TODO: Verify objective, optimizer, schedule, and inference procedure from the paper.",
            "    update_or_collect(outputs, loss_or_score)",
        ]),
        "evaluation": "\n".join([
            "evaluation_outputs = run_evaluation(model, paper_inputs)",
            "metrics = compute_reported_metrics(evaluation_outputs)",
            "# TODO: Match metrics, datasets, baselines, and expected result ranges to the paper.",
        ]),
        "extension_points": "\n".join([
            "# Explicit gaps to resolve before converting this scaffold into runnable code:",
            *gap_lines,
        ]),
    }


def _algorithm_step_pseudocode_lines(
    algorithm_steps: list[dict[str, Any]],
) -> list[str]:
    if not algorithm_steps:
        return ["# TODO: No grounded algorithm steps were available."]

    lines = []
    for step in algorithm_steps:
        order = step.get("order") or len(lines) + 1
        title = _coerce_text(step.get("title"), f"Algorithm step {order}")
        description = _coerce_text(step.get("description"), NOT_EXPLICITLY_DISCLOSED)
        lines.extend([
            f"# Step {order}: {title}",
            f"# Grounded detail: {_clip_text(description, 240)}",
            "apply_step(model, paper_inputs)",
        ])
    return lines


def _gap_todo_lines(assumptions_and_gaps: list[dict[str, Any]]) -> list[str]:
    if not assumptions_and_gaps:
        return ["# TODO: Re-check the original paper for any missing implementation details."]

    lines = []
    for gap in assumptions_and_gaps:
        category = _normalize_gap_category(gap.get("category"), "")
        description = _coerce_text(gap.get("description"), NOT_EXPLICITLY_DISCLOSED)
        lines.append(f"# TODO [{category}]: {_clip_text(description, 240)}")
    return lines


def _format_pseudocode_sections(sections: dict[str, str]) -> str:
    return "\n\n".join([
        f"## Setup\n{sections['setup'].strip()}",
        f"## Model\n{sections['model'].strip()}",
        f"## Training / Inference\n{sections['training_or_inference'].strip()}",
        f"## Evaluation\n{sections['evaluation'].strip()}",
        f"## Extension Points\n{sections['extension_points'].strip()}",
    ])


def _normalize_starter_code_files(
    value: object,
    fallback_files: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
    target_framework: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list):
        return [], []

    files = []
    warnings = []
    seen_paths: set[str] = set()
    total_chars = 0

    for item in value:
        if len(files) >= MAX_STARTER_CODE_FILES:
            break
        if not isinstance(item, dict):
            continue

        path, path_warning = _normalize_starter_code_path(item.get("path"))
        if path_warning:
            warnings.append(path_warning)
        if not path or path in seen_paths:
            if path in seen_paths:
                warnings.append(f"Duplicate starter code path skipped: {path}.")
            continue

        content = _coerce_text(item.get("content"), "")
        if not content:
            warnings.append(f"Starter code file skipped because content was empty: {path}.")
            continue
        if len(content) > MAX_STARTER_FILE_CHARS:
            warnings.append(f"Starter code file skipped because content was too large: {path}.")
            continue
        if total_chars + len(content) > MAX_STARTER_CODE_TOTAL_CHARS:
            warnings.append(
                f"Starter code file skipped because the total code payload was too large: {path}."
            )
            continue

        language = _starter_language_for_path(path)
        purpose = _coerce_text(
            item.get("purpose"),
            _default_starter_file_purpose(path, target_framework),
        )
        normalized_file = {
            "path": path,
            "language": language,
            "purpose": purpose,
            "content": content,
        }

        if language == "python":
            normalized_file, syntax_warning = _replace_invalid_python_starter_file(
                normalized_file,
                assumptions_and_gaps,
            )
            if syntax_warning:
                warnings.append(syntax_warning)

        files.append(normalized_file)
        seen_paths.add(path)
        total_chars += len(normalized_file["content"])

    if not files:
        return [], _dedupe_strings(warnings)

    for fallback_file in fallback_files:
        if len(files) >= MIN_STARTER_CODE_FILES:
            break
        path = fallback_file["path"]
        if path in seen_paths:
            continue
        files.append(fallback_file)
        seen_paths.add(path)

    files = files[:MAX_STARTER_CODE_FILES]
    files = _ensure_gap_todos_in_starter_code(files, assumptions_and_gaps)
    return files, _dedupe_strings(warnings)


def _starter_payload_conflicts_with_target_framework(
    starter_code: list[dict[str, Any]],
    setup_notes: list[str],
    test_plan: list[str],
    target_framework: str,
) -> bool:
    if target_framework != "generic-python":
        return False

    combined_text = "\n".join([
        *[file.get("path", "") for file in starter_code],
        *[file.get("purpose", "") for file in starter_code],
        *[file.get("content", "") for file in starter_code],
        *setup_notes,
        *test_plan,
    ]).lower()

    return any(
        token in combined_text
        for token in (
            "pytorch",
            "import torch",
            "from torch",
            "torch.",
            "nn.module",
            "torch.utils",
        )
    )


def _normalize_starter_code_path(value: object) -> tuple[str | None, str | None]:
    path = str(value or "").strip().replace("\\", "/")
    if not path:
        return None, "Starter code file skipped because path was empty."
    if path.startswith("/") or path.startswith("~"):
        return None, f"Starter code file skipped because path was absolute: {path}."
    if "\x00" in path:
        return None, "Starter code file skipped because path contained an invalid character."

    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None, f"Starter code file skipped because path was unsafe: {path}."
    if any(part.startswith(".") for part in parts):
        return None, f"Starter code file skipped because hidden paths are not allowed: {path}."
    if not any(path.endswith(extension) for extension in SUPPORTED_STARTER_EXTENSIONS):
        return None, f"Starter code file skipped because extension is unsupported: {path}."

    return path, None


def _starter_language_for_path(path: str) -> str:
    if path.endswith(".md"):
        return "markdown"
    return "python"


def _default_starter_file_purpose(path: str, target_framework: str) -> str:
    if path == "README.md":
        return "Explain the starter scaffold, assumptions, and unresolved TODOs."
    if path.endswith("data.py"):
        return "Define local data loading and batch-shaping placeholders."
    if path.endswith("model.py"):
        return f"Define the {target_framework} model placeholder."
    if path.endswith("train.py"):
        return "Sketch a local training or inference loop."
    if path.endswith("pipeline.py"):
        return "Sketch the generic Python implementation pipeline."
    if path.endswith("tests_smoke.py"):
        return "Provide lightweight smoke checks for the scaffold."
    return "Starter scaffold file."


def _replace_invalid_python_starter_file(
    file: dict[str, Any],
    assumptions_and_gaps: list[dict[str, Any]],
) -> tuple[dict[str, Any], str | None]:
    try:
        ast.parse(file["content"])
    except SyntaxError:
        return (
            {
                **file,
                "content": _safe_python_placeholder(
                    file["path"],
                    "invalid Python syntax",
                    assumptions_and_gaps,
                ),
            },
            f"{file['path']} was replaced because generated Python did not parse.",
        )

    return file, None


def _ensure_gap_todos_in_starter_code(
    files: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not files or not assumptions_and_gaps:
        return files

    combined_content = "\n".join(file.get("content", "") for file in files).lower()
    if "unresolved paper details" in combined_content:
        return files

    markdown_todos = _gap_markdown_todo_lines(assumptions_and_gaps)
    updated_files = [dict(file) for file in files]

    for file in updated_files:
        if file["path"] == "README.md":
            file["content"] = "\n\n".join([
                file["content"].rstrip(),
                "## Unresolved Paper Details",
                "\n".join(markdown_todos),
            ])
            return updated_files

    if len(updated_files) < MAX_STARTER_CODE_FILES:
        updated_files.insert(0, {
            "path": "README.md",
            "language": "markdown",
            "purpose": "Explain unresolved paper details for the starter scaffold.",
            "content": "\n".join([
                "# Starter Implementation Scaffold",
                "",
                "Generated starter code is a scaffold, not a verified reproduction.",
                "",
                "## Unresolved Paper Details",
                *markdown_todos,
            ]),
        })
        return updated_files

    first_file = updated_files[0]
    comment_prefix = "#" if first_file["language"] == "python" else ""
    todo_block = [
        f"{comment_prefix} Unresolved Paper Details".strip(),
        *[
            f"{comment_prefix} {line}".strip()
            for line in markdown_todos
        ],
    ]
    first_file["content"] = "\n\n".join([
        first_file["content"].rstrip(),
        "\n".join(todo_block),
    ])
    return updated_files


def _gap_markdown_todo_lines(
    assumptions_and_gaps: list[dict[str, Any]],
) -> list[str]:
    lines = []
    for gap in assumptions_and_gaps:
        category = _normalize_gap_category(gap.get("category"), "")
        description = _coerce_text(gap.get("description"), NOT_EXPLICITLY_DISCLOSED)
        lines.append(f"- TODO [{category}]: {_clip_text(description, 240)}")
    return lines or ["- TODO: Re-check the original paper for missing implementation details."]


def _build_deterministic_starter_code_payload(
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
    pseudocode: str,
    focus: str | None,
    target_framework: str,
) -> dict[str, Any]:
    return {
        "starter_code": _build_deterministic_starter_files(
            implementation_context=implementation_context,
            algorithm_steps=algorithm_steps,
            assumptions_and_gaps=assumptions_and_gaps,
            pseudocode=pseudocode,
            focus=focus,
            target_framework=target_framework,
        ),
        "setup_notes": _build_deterministic_setup_notes(target_framework),
        "test_plan": _build_deterministic_test_plan(target_framework),
    }


def _build_deterministic_starter_files(
    implementation_context: dict[str, Any],
    algorithm_steps: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
    pseudocode: str,
    focus: str | None,
    target_framework: str,
) -> list[dict[str, Any]]:
    paper = implementation_context.get("paper") or {}
    title = paper.get("title") or "the paper"
    step_lines = _starter_step_comment_lines(algorithm_steps)
    gap_lines = _gap_python_todo_lines(assumptions_and_gaps)
    markdown_todos = _gap_markdown_todo_lines(assumptions_and_gaps)
    focus_line = focus or "full method scaffold"
    pseudocode_note = _clip_text(pseudocode.replace("\n", " "), 500)

    readme = {
        "path": "README.md",
        "language": "markdown",
        "purpose": "Explain the starter scaffold, assumptions, and unresolved TODOs.",
        "content": "\n".join([
            f"# Starter Scaffold for {title}",
            "",
            "This is starter code generated from grounded paper context. It is not a verified reproduction.",
            f"- Target framework: {target_framework}",
            f"- Focus: {focus_line}",
            "",
            "## Files",
            *_starter_readme_file_lines(target_framework),
            "",
            "## Pseudocode Basis",
            pseudocode_note or "TODO: Reconstruct pseudocode from the original paper.",
            "",
            "## Unresolved Paper Details",
            *markdown_todos,
        ]),
    }
    data_file = {
        "path": "data.py",
        "language": "python",
        "purpose": "Define local data loading and batch-shaping placeholders.",
        "content": _starter_data_py(title, gap_lines),
    }

    if target_framework == "generic-python":
        return [
            readme,
            data_file,
            {
                "path": "pipeline.py",
                "language": "python",
                "purpose": "Sketch the generic Python implementation pipeline.",
                "content": _starter_pipeline_py(title, step_lines, gap_lines),
            },
            {
                "path": "tests_smoke.py",
                "language": "python",
                "purpose": "Provide lightweight smoke checks for the scaffold.",
                "content": _starter_tests_smoke_py(),
            },
        ]

    return [
        readme,
        data_file,
        {
            "path": "model.py",
            "language": "python",
            "purpose": "Define the PyTorch model placeholder.",
            "content": _starter_model_py(title, step_lines, gap_lines),
        },
        {
            "path": "train.py",
            "language": "python",
            "purpose": "Sketch a local training or inference loop.",
            "content": _starter_train_py(step_lines, gap_lines),
        },
    ]


def _starter_readme_file_lines(target_framework: str) -> list[str]:
    if target_framework == "generic-python":
        return [
            "- `data.py`: local data adapter placeholders.",
            "- `pipeline.py`: generic implementation pipeline placeholders.",
            "- `tests_smoke.py`: lightweight checks to adapt after filling TODOs.",
        ]
    return [
        "- `data.py`: local data adapter placeholders.",
        "- `model.py`: PyTorch module placeholder.",
        "- `train.py`: training or inference loop placeholder.",
    ]


def _starter_step_comment_lines(algorithm_steps: list[dict[str, Any]]) -> list[str]:
    if not algorithm_steps:
        return ["# TODO: No grounded algorithm steps were available."]

    lines = []
    for step in algorithm_steps:
        order = step.get("order") or len(lines) + 1
        title = _coerce_text(step.get("title"), f"Algorithm step {order}")
        description = _coerce_text(step.get("description"), NOT_EXPLICITLY_DISCLOSED)
        lines.extend([
            f"# Step {order}: {title}",
            f"# TODO: Implement only after verifying this grounded detail: {_clip_text(description, 220)}",
        ])
    return lines


def _gap_python_todo_lines(assumptions_and_gaps: list[dict[str, Any]]) -> list[str]:
    markdown_lines = _gap_markdown_todo_lines(assumptions_and_gaps)
    return [f"# {line.removeprefix('- ')}" for line in markdown_lines]


def _starter_data_py(title: str, gap_lines: list[str]) -> str:
    return "\n".join([
        '"""Local data placeholders for a PaperTrail starter scaffold."""',
        "",
        "from dataclasses import dataclass",
        "from typing import Iterable",
        "",
        "",
        "@dataclass",
        "class PaperBatch:",
        "    inputs: object",
        "    targets: object | None = None",
        "",
        "",
        "def load_local_examples() -> list[object]:",
        f"    \"\"\"Load local examples for {title}.\"\"\"",
        "    # TODO: Replace with local data prepared from the paper's described dataset.",
        "    return []",
        "",
        "",
        "def iter_batches(examples: list[object], batch_size: int = 1) -> Iterable[PaperBatch]:",
        "    # TODO: Map examples into tensors or Python objects matching the paper.",
        "    if not examples:",
        "        return",
        "    for start in range(0, len(examples), batch_size):",
        "        chunk = examples[start:start + batch_size]",
        "        yield PaperBatch(inputs=chunk)",
        "",
        *_dedupe_strings(gap_lines),
        "",
    ])


def _starter_model_py(
    title: str,
    step_lines: list[str],
    gap_lines: list[str],
) -> str:
    return "\n".join([
        '"""PyTorch model placeholder for a PaperTrail starter scaffold."""',
        "",
        "from __future__ import annotations",
        "",
        "try:",
        "    import torch",
        "    from torch import nn",
        "except ImportError as error:",
        "    raise ImportError(\"Install PyTorch before running this scaffold.\") from error",
        "",
        "",
        "class PaperModel(nn.Module):",
        f"    \"\"\"Starter model shell for {title}.\"\"\"",
        "",
        "    def __init__(self) -> None:",
        "        super().__init__()",
        "        # TODO: Add layers only where the paper specifies architecture details.",
        "",
        "    def forward(self, batch: object) -> object:",
        "        # TODO: Replace with the paper-specific forward computation.",
        "        raise NotImplementedError(\"TODO: fill the grounded model computation.\")",
        "",
        "",
        "def compute_objective(outputs: object, batch: object) -> object:",
        "    # TODO: Implement the paper's objective or loss after verifying equations.",
        "    raise NotImplementedError(\"TODO: fill the grounded objective or scoring function.\")",
        "",
        *_dedupe_strings(step_lines),
        *_dedupe_strings(gap_lines),
        "",
    ])


def _starter_train_py(
    step_lines: list[str],
    gap_lines: list[str],
) -> str:
    return "\n".join([
        '"""Training or inference loop placeholder for a PaperTrail starter scaffold."""',
        "",
        "from data import iter_batches, load_local_examples",
        "from model import PaperModel, compute_objective",
        "",
        "",
        "def run_scaffold() -> None:",
        "    examples = load_local_examples()",
        "    model = PaperModel()",
        "    # TODO: Configure optimizer, schedule, device, and stopping criteria from the paper.",
        "    for batch in iter_batches(examples):",
        "        outputs = model(batch)",
        "        objective = compute_objective(outputs, batch)",
        "        # TODO: Decide whether this loop trains, evaluates, or collects inference outputs.",
        "        _ = objective",
        "",
        "",
        "if __name__ == \"__main__\":",
        "    run_scaffold()",
        "",
        *_dedupe_strings(step_lines),
        *_dedupe_strings(gap_lines),
        "",
    ])


def _starter_pipeline_py(
    title: str,
    step_lines: list[str],
    gap_lines: list[str],
) -> str:
    return "\n".join([
        '"""Generic Python pipeline placeholder for a PaperTrail starter scaffold."""',
        "",
        "from data import iter_batches, load_local_examples",
        "",
        "",
        "def build_components() -> dict[str, object]:",
        f"    \"\"\"Create implementation components for {title}.\"\"\"",
        "    # TODO: Fill components only where the paper explicitly specifies them.",
        "    return {}",
        "",
        "",
        "def run_pipeline() -> list[object]:",
        "    examples = load_local_examples()",
        "    components = build_components()",
        "    outputs: list[object] = []",
        "    for batch in iter_batches(examples):",
        "        # TODO: Translate grounded algorithm steps into concrete transformations.",
        "        outputs.append({\"batch\": batch, \"components\": components})",
        "    return outputs",
        "",
        *_dedupe_strings(step_lines),
        *_dedupe_strings(gap_lines),
        "",
    ])


def _starter_tests_smoke_py() -> str:
    return "\n".join([
        '"""Smoke checks for a generic PaperTrail starter scaffold."""',
        "",
        "from pipeline import build_components",
        "",
        "",
        "def test_build_components_returns_mapping() -> None:",
        "    components = build_components()",
        "    assert isinstance(components, dict)",
        "    # TODO: Add paper-specific shape, metric, or output checks after filling the scaffold.",
        "",
    ])


def _build_deterministic_setup_notes(target_framework: str) -> list[str]:
    notes = [
        "Generated files are starter scaffold text only; PaperTrail does not write them to disk or execute them.",
        "Resolve every TODO against the original paper before treating the scaffold as runnable.",
    ]
    if target_framework == "pytorch":
        notes.append("Install a PyTorch build appropriate for your local hardware before running the scaffold.")
    else:
        notes.append("The generic Python scaffold avoids framework-specific dependencies by default.")
    return notes


def _build_deterministic_test_plan(target_framework: str) -> list[str]:
    py_compile_target = "data.py model.py train.py"
    if target_framework == "generic-python":
        py_compile_target = "data.py pipeline.py tests_smoke.py"
    return [
        f"After materializing the files locally, run `python -m py_compile {py_compile_target}`.",
        "Fill TODOs with paper-grounded details, then run a tiny synthetic-input smoke test.",
        "Compare scaffold outputs, metrics, and assumptions against the paper before any real experiment.",
    ]


def _review_starter_code_deterministically(
    starter_code: list[dict[str, Any]],
    assumptions_and_gaps: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    reviewed_files = []
    warnings = []

    for file in starter_code:
        reasons = _unsafe_starter_code_reasons(file.get("content", ""))
        if reasons:
            reviewed_files.append(
                _safe_replacement_starter_file(file, reasons, assumptions_and_gaps)
            )
            warnings.append(
                f"{file.get('path', 'Starter code file')} was replaced because starter code contained unsafe or out-of-scope behavior: {', '.join(reasons)}."
            )
            continue
        reviewed_files.append(file)

    return reviewed_files, _dedupe_strings(warnings)


def _unsafe_starter_code_reasons(content: str) -> list[str]:
    normalized = content.lower()
    pattern_groups = (
        (
            "network calls",
            (
                "requests.",
                "urllib.",
                "httpx.",
                "aiohttp.",
                "socket.",
                "urlopen(",
                "urlretrieve(",
            ),
        ),
        (
            "dataset downloads",
            (
                "load_dataset(",
                ".download(",
                "download_url(",
                "download_and_extract",
                "wget ",
                "curl ",
            ),
        ),
        (
            "shell or process execution",
            (
                "subprocess",
                "os.system(",
                "os.popen(",
                "popen(",
                "spawn(",
            ),
        ),
        ("dynamic code execution", ("eval(", "exec(")),
        (
            "API key or provider usage",
            (
                "api_key",
                "apikey",
                "secret_key",
                "openai",
                "anthropic",
                "google.generativeai",
                "gemini",
                "llm_provider",
            ),
        ),
    )

    reasons = []
    for label, tokens in pattern_groups:
        if any(token in normalized for token in tokens):
            reasons.append(label)
    return reasons


def _safe_replacement_starter_file(
    file: dict[str, Any],
    reasons: list[str],
    assumptions_and_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    path = _coerce_text(file.get("path"), "starter_placeholder.py")
    language = _starter_language_for_path(path)
    reason_text = ", ".join(reasons)
    if language == "markdown":
        content = "\n".join([
            "# Replaced Starter File",
            "",
            f"This file was replaced because it contained unsafe or out-of-scope behavior: {reason_text}.",
            "",
            "## TODO",
            *_gap_markdown_todo_lines(assumptions_and_gaps),
        ])
    else:
        content = _safe_python_placeholder(path, reason_text, assumptions_and_gaps)

    return {
        "path": path,
        "language": language,
        "purpose": _coerce_text(
            file.get("purpose"),
            "Safe placeholder for replaced starter code.",
        ),
        "content": content,
    }


def _safe_python_placeholder(
    path: str,
    reason: str,
    assumptions_and_gaps: list[dict[str, Any]],
) -> str:
    return "\n".join([
        f'"""Safe placeholder for {path}."""',
        "",
        f"# Replaced because: {reason}.",
        "# TODO: Regenerate or rewrite this file using only grounded paper details.",
        *_gap_python_todo_lines(assumptions_and_gaps),
        "",
        "",
        "def placeholder() -> None:",
        "    raise NotImplementedError(\"TODO: replace this safe placeholder with grounded implementation code.\")",
        "",
    ])


def _build_deterministic_algorithm_steps(
    implementation_context: dict[str, Any],
) -> list[dict[str, Any]]:
    steps = []
    breakdown = implementation_context.get("structured_breakdown") or {}
    method = breakdown.get("method")
    relevant_sections = [
        section
        for section in implementation_context.get("relevant_sections", [])
        if isinstance(section, dict)
    ]

    if method and method != NOT_EXPLICITLY_DISCLOSED:
        steps.append({
            "order": len(steps) + 1,
            "title": "Implement the described method",
            "description": method,
            "inputs": _fallback_inputs(implementation_context),
            "outputs": _fallback_outputs(implementation_context),
            "evidence": ["Structured breakdown: method"],
        })

    for section in relevant_sections:
        if len(steps) >= 4:
            break
        title = str(section.get("title", "")).strip() or "Paper section"
        content = str(section.get("content", "")).strip()
        if not content:
            continue
        if not _section_title_matches_method_context(title) and steps:
            continue
        steps.append({
            "order": len(steps) + 1,
            "title": f"Translate {title} into implementation steps",
            "description": _clip_text(content, 480),
            "inputs": _fallback_inputs(implementation_context),
            "outputs": _fallback_outputs(implementation_context),
            "evidence": [title],
        })

    for index, step in enumerate(steps):
        step["order"] = index + 1

    return steps


def _build_fallback_implementation_summary(
    paper: Paper,
    implementation_context: dict[str, Any],
) -> str:
    step_source_count = len(implementation_context.get("relevant_sections") or [])
    return (
        f"Extracted a Phase 9C implementation-oriented algorithm outline for {paper.title} "
        f"from {step_source_count} grounded source section(s). Gap analysis and pseudocode "
        "are included, with starter-code scaffolding added when enough context is available."
    )


def _add_focus_to_summary(summary: str, focus: str | None) -> str:
    if not focus:
        return summary
    if f"Requested focus: {focus}." in summary:
        return summary
    return f"{summary} Requested focus: {focus}."


def _fallback_inputs(implementation_context: dict[str, Any]) -> list[str]:
    paper = implementation_context.get("paper") or {}
    title = paper.get("title") or "the paper"
    return [
        f"Paper-specific inputs described by {title}; exact tensors/data formats may need confirmation."
    ]


def _fallback_outputs(implementation_context: dict[str, Any]) -> list[str]:
    breakdown = implementation_context.get("structured_breakdown") or {}
    results = breakdown.get("results")
    if results and results != NOT_EXPLICITLY_DISCLOSED:
        return [results]
    return ["Outputs are not fully specified in the provided paper context."]


def _fallback_evidence(implementation_context: dict[str, Any]) -> list[str]:
    sections = implementation_context.get("relevant_sections") or []
    evidence = [
        str(section.get("title", "")).strip()
        for section in sections
        if isinstance(section, dict) and str(section.get("title", "")).strip()
    ]
    if evidence:
        return evidence[:3]
    return ["Structured breakdown"]


def _append_gap(
    gaps: list[dict[str, Any]],
    category: str,
    description: str,
    severity: str,
    evidence: list[str],
) -> None:
    normalized_description = _coerce_text(description, "")
    if not normalized_description:
        return

    gaps.append({
        "category": _normalize_gap_category(category, normalized_description),
        "description": normalized_description,
        "severity": _normalize_gap_severity(severity, normalized_description),
        "evidence": _dedupe_strings(evidence) or ["Provided paper context"],
    })


def _dedupe_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen = set()
    for gap in gaps:
        category = _normalize_gap_category(gap.get("category"), "")
        description = _coerce_text(gap.get("description"), "")
        if not description:
            continue
        key = (category, description.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append({
            "category": category,
            "description": description,
            "severity": _normalize_gap_severity(gap.get("severity"), description),
            "evidence": _normalize_string_list(gap.get("evidence"))
            or ["Provided paper context"],
        })
    return deduped


def _normalize_gap_category(value: object, description: str) -> str:
    normalized = str(value or "").strip()
    if normalized in GAP_CATEGORIES:
        return normalized
    return _classify_gap_category(description)


def _normalize_gap_severity(value: object, description: str) -> str:
    normalized = str(value or "").strip()
    if normalized in GAP_SEVERITIES:
        return normalized
    return _severity_from_text(description)


def _classify_gap_category(text: str) -> str:
    normalized = text.lower()
    if any(
        token in normalized
        for token in (
            "hyperparameter",
            "learning rate",
            "batch size",
            "epoch",
            "optimizer",
            "schedule",
            "stopping",
        )
    ):
        return "hyperparameters"
    if any(
        token in normalized
        for token in ("equation", "loss", "objective", "formula", "derivation")
    ):
        return "equations"
    if any(
        token in normalized
        for token in (
            "dataset",
            "data",
            "input",
            "tensor",
            "feature",
            "preprocess",
            "batch",
            "label",
        )
    ):
        return "data"
    if any(
        token in normalized
        for token in ("evaluation", "metric", "benchmark", "baseline", "result", "output")
    ):
        return "evaluation"
    if any(
        token in normalized
        for token in (
            "dependency",
            "environment",
            "package",
            "library",
            "framework",
            "runtime",
            "install",
            "provider",
            "model generation",
            "extraction failed",
            "fallback",
        )
    ):
        return "environment_dependencies"
    return "model_architecture"


def _severity_from_text(text: str) -> str:
    normalized = text.lower()
    if any(
        token in normalized
        for token in (
            "no ",
            "missing",
            "not explicitly",
            "unavailable",
            "unknown",
            "sparse",
        )
    ):
        return "high"
    if any(
        token in normalized
        for token in ("not fully", "may need", "verify", "confirm", "fallback")
    ):
        return "medium"
    return "low"


def _is_unspecified_text(text: str) -> bool:
    normalized = text.lower()
    return (
        text == NOT_EXPLICITLY_DISCLOSED
        or "not explicitly" in normalized
        or "not fully specified" in normalized
        or "may need confirmation" in normalized
        or "missing" in normalized
        or "unavailable" in normalized
        or "unknown" in normalized
        or "todo" in normalized
    )


def _has_gap_category(gaps: list[dict[str, Any]], category: str) -> bool:
    return any(gap.get("category") == category for gap in gaps)


def _step_text(step: dict[str, Any]) -> str:
    parts = [
        str(step.get("title") or ""),
        str(step.get("description") or ""),
        *[str(item) for item in step.get("inputs") or []],
        *[str(item) for item in step.get("outputs") or []],
    ]
    return " ".join(parts)


def _algorithm_step_evidence(
    algorithm_steps: list[dict[str, Any]],
    fallback_evidence: list[str],
) -> list[str]:
    evidence = []
    for step in algorithm_steps:
        evidence.extend(_normalize_string_list(step.get("evidence")))
    return _dedupe_strings(evidence) or fallback_evidence


def _normalize_breakdown(breakdown: dict | None) -> dict[str, str]:
    normalized = dict(breakdown or {})
    for field in BREAKDOWN_FIELDS:
        normalized[field] = _coerce_text(
            normalized.get(field),
            NOT_EXPLICITLY_DISCLOSED,
        )
    return normalized


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return _dedupe_strings(
        [str(item).strip() for item in value if str(item).strip()]
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _coerce_text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _section_title_matches_method_context(section_title: str) -> bool:
    normalized_title = section_title.lower()
    return any(keyword in normalized_title for keyword in METHOD_SECTION_KEYWORDS)


def _serialize_source_section(section: PaperSection) -> dict[str, Any]:
    return {
        "id": str(section.id),
        "title": section.section_title,
        "section_order": section.section_order,
        "content_preview": _clip_text(section.content, MAX_SECTION_PREVIEW_CHARS),
    }


def _serialize_implementation_paper(paper: Paper) -> dict[str, str | None]:
    return {
        "id": str(paper.id),
        "title": paper.title,
        "authors": paper.authors,
        "arxiv_url": paper.arxiv_url,
        "created_at": paper.created_at.isoformat() if paper.created_at else "",
    }


def _clip_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value

    return f"{value[: max_chars - 3].rstrip()}..."
