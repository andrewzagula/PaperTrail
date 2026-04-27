from __future__ import annotations

import uuid
from dataclasses import dataclass
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


IdeaGraphNode = Callable[[IdeaGraphState], IdeaGraphState]


@dataclass(frozen=True)
class IdeaGraphNodes:
    load_sources: IdeaGraphNode
    ensure_breakdowns: IdeaGraphNode
    normalize_context: IdeaGraphNode
    generate_candidates: IdeaGraphNode
    critique_and_filter: IdeaGraphNode
    build_response: IdeaGraphNode


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
    graph.add_edge("critique_and_filter", "build_response")
    graph.add_edge("build_response", END)

    return graph.compile()
