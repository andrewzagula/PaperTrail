from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, TypedDict

from langgraph.graph import END, StateGraph

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


class IdeaGraphState(TypedDict, total=False):
    db: Any
    user_id: uuid.UUID
    paper_ids: list[uuid.UUID]
    topic: str | None
    papers: list[Any]
    paper_contexts: list[dict[str, Any]]
    selected_papers: list[dict[str, Any]]
    source_topic: str | None
    idea_context: dict[str, Any]
    candidate_ideas: list[dict[str, Any]]
    ideas: list[dict[str, Any]]
    warnings: list[str]
    # Retry bookkeeping. generation_attempts counts completed candidate
    # generation passes; used_deterministic_candidates records whether the
    # last pass fell back to templates, which are not worth regenerating.
    generation_attempts: int
    used_deterministic_candidates: bool


IdeaGraphNode = Callable[[IdeaGraphState], IdeaGraphState]
IdeaGraphDecision = Callable[[IdeaGraphState], bool]


def _never_retry(state: IdeaGraphState) -> bool:
    return False


@dataclass(frozen=True)
class IdeaGraphNodes:
    load_sources: IdeaGraphNode
    ensure_breakdowns: IdeaGraphNode
    normalize_context: IdeaGraphNode
    generate_candidates: IdeaGraphNode
    critique_and_filter: IdeaGraphNode
    build_response: IdeaGraphNode
    # Decides whether too few ideas survived critique to accept the result.
    # Defaults to a straight-through run so callers that do not supply a
    # policy keep the original linear behaviour.
    should_retry_candidates: IdeaGraphDecision = field(default=_never_retry)


def build_idea_graph(nodes: IdeaGraphNodes) -> CompiledStateGraph:
    graph = StateGraph(IdeaGraphState)

    graph.add_node("load_sources", nodes.load_sources)
    graph.add_node("ensure_breakdowns", nodes.ensure_breakdowns)
    graph.add_node("normalize_context", nodes.normalize_context)
    graph.add_node("generate_candidates", nodes.generate_candidates)
    graph.add_node("critique_and_filter", nodes.critique_and_filter)
    graph.add_node("build_response", nodes.build_response)

    graph.set_entry_point("load_sources")
    graph.add_edge("load_sources", "ensure_breakdowns")
    graph.add_edge("ensure_breakdowns", "normalize_context")
    graph.add_edge("normalize_context", "generate_candidates")
    graph.add_edge("generate_candidates", "critique_and_filter")

    # Loop back for another candidate pass when critique left too few ideas,
    # instead of returning a thin result on a single unlucky generation.
    graph.add_conditional_edges(
        "critique_and_filter",
        lambda state: "retry" if nodes.should_retry_candidates(state) else "accept",
        {"retry": "generate_candidates", "accept": "build_response"},
    )

    graph.add_edge("build_response", END)

    return graph.compile()
