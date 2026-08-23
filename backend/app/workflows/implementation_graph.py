from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, TypedDict

from langgraph.graph import END, StateGraph

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


class ImplementationGraphState(TypedDict, total=False):
    db: Any
    user_id: uuid.UUID
    paper_id: uuid.UUID
    focus: str | None
    target_language: str
    target_framework: str
    paper: Any
    sections: list[Any]
    breakdown: dict[str, Any]
    implementation_context: dict[str, Any]
    source_sections: list[dict[str, Any]]
    implementation_summary: str
    algorithm_steps: list[dict[str, Any]]
    assumptions_and_gaps: list[dict[str, Any]]
    pseudocode: str
    starter_code: list[dict[str, Any]]
    setup_notes: list[str]
    test_plan: list[str]
    warnings: list[str]
    # Regeneration bookkeeping. code_generation_attempts counts completed
    # starter code passes; unsafe_code_feedback carries the paths and reasons
    # the safety review rejected, so a retry can be told what to avoid.
    code_generation_attempts: int
    used_deterministic_starter_code: bool
    unsafe_code_feedback: list[dict[str, Any]]
    review_warnings: list[str]


ImplementationGraphNode = Callable[[ImplementationGraphState], ImplementationGraphState]
ImplementationGraphDecision = Callable[[ImplementationGraphState], bool]


def _never_regenerate(state: ImplementationGraphState) -> bool:
    return False


@dataclass(frozen=True)
class ImplementationGraphNodes:
    load_paper: ImplementationGraphNode
    prepare_context: ImplementationGraphNode
    extract_algorithm: ImplementationGraphNode
    analyze_gaps: ImplementationGraphNode
    generate_pseudocode: ImplementationGraphNode
    generate_starter_code: ImplementationGraphNode
    review_scaffold: ImplementationGraphNode
    build_response: ImplementationGraphNode
    # Decides whether the safety review rejected enough of the generated code
    # to be worth asking the model again. Defaults to a straight-through run.
    should_regenerate_starter_code: ImplementationGraphDecision = field(
        default=_never_regenerate
    )


def build_implementation_graph(
    nodes: ImplementationGraphNodes,
) -> CompiledStateGraph:
    graph = StateGraph(ImplementationGraphState)

    graph.add_node("load_paper", nodes.load_paper)
    graph.add_node("prepare_context", nodes.prepare_context)
    graph.add_node("extract_algorithm", nodes.extract_algorithm)
    graph.add_node("analyze_gaps", nodes.analyze_gaps)
    graph.add_node("generate_pseudocode", nodes.generate_pseudocode)
    graph.add_node("generate_starter_code", nodes.generate_starter_code)
    graph.add_node("review_scaffold", nodes.review_scaffold)
    graph.add_node("build_response", nodes.build_response)

    graph.set_entry_point("load_paper")
    graph.add_edge("load_paper", "prepare_context")
    graph.add_edge("prepare_context", "extract_algorithm")
    graph.add_edge("extract_algorithm", "analyze_gaps")
    graph.add_edge("analyze_gaps", "generate_pseudocode")
    graph.add_edge("generate_pseudocode", "generate_starter_code")
    graph.add_edge("generate_starter_code", "review_scaffold")

    # Regenerate rather than shipping safe-but-empty placeholders when the
    # review had to strip unsafe code out of the model's output.
    graph.add_conditional_edges(
        "review_scaffold",
        lambda state: (
            "regenerate"
            if nodes.should_regenerate_starter_code(state)
            else "accept"
        ),
        {"regenerate": "generate_starter_code", "accept": "build_response"},
    )
    graph.add_edge("build_response", END)

    return graph.compile()
