from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, TypedDict

from langgraph.graph import END, StateGraph

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


class CompareGraphState(TypedDict, total=False):
    db: Any
    user_id: uuid.UUID
    paper_ids: list[uuid.UUID]
    papers: list[Any]
    paper_contexts: list[dict[str, Any]]
    selected_papers: list[dict[str, Any]]
    normalized_profiles: list[dict[str, Any]]
    narrative_summary: str
    warnings: list[str]
    comparison_table: dict[str, Any]


CompareGraphNode = Callable[[CompareGraphState], CompareGraphState]
CompareGraphDecision = Callable[[CompareGraphState], bool]


def _never_widen(state: CompareGraphState) -> bool:
    return False


def _passthrough(state: CompareGraphState) -> CompareGraphState:
    return {}


@dataclass(frozen=True)
class CompareGraphNodes:
    load_papers: CompareGraphNode
    ensure_breakdowns: CompareGraphNode
    normalize_profiles: CompareGraphNode
    synthesize_narrative: CompareGraphNode
    build_response: CompareGraphNode
    # Alternative context strategy for papers whose title-selected sections did
    # not yield a usable profile. Skipped entirely on the normal path.
    widen_context: CompareGraphNode = field(default=_passthrough)
    should_widen_context: CompareGraphDecision = field(default=_never_widen)


def build_compare_graph(nodes: CompareGraphNodes) -> CompiledStateGraph:
    graph = StateGraph(CompareGraphState)

    graph.add_node("load_papers", nodes.load_papers)
    graph.add_node("ensure_breakdowns", nodes.ensure_breakdowns)
    graph.add_node("normalize_profiles", nodes.normalize_profiles)
    graph.add_node("synthesize_narrative", nodes.synthesize_narrative)
    graph.add_node("widen_context", nodes.widen_context)
    graph.add_node("build_response", nodes.build_response)

    graph.set_entry_point("load_papers")
    graph.add_edge("load_papers", "ensure_breakdowns")
    graph.add_edge("ensure_breakdowns", "normalize_profiles")
    # A sparse profile is only visible after profiling, so widening loops back
    # rather than branching ahead. The decision refuses a paper it has already
    # widened, which is what terminates the cycle.
    graph.add_conditional_edges(
        "normalize_profiles",
        lambda state: "widen" if nodes.should_widen_context(state) else "accept",
        {"widen": "widen_context", "accept": "synthesize_narrative"},
    )
    graph.add_edge("widen_context", "normalize_profiles")
    graph.add_edge("synthesize_narrative", "build_response")
    graph.add_edge("build_response", END)

    return graph.compile()
