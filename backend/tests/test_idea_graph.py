import importlib
import unittest
import uuid
from unittest.mock import Mock, patch

from fastapi import HTTPException
from app.services.paper_ideas import generate_paper_ideas
from app.workflows.idea_graph import (
    IdeaGraphNodes,
    build_idea_graph,
)


class IdeaGraphFoundationTests(unittest.TestCase):
    def test_idea_graph_module_imports_and_exports_foundation_symbols(self):
        idea_graph = importlib.import_module("app.workflows.idea_graph")
        workflows = importlib.import_module("app.workflows")

        self.assertTrue(hasattr(idea_graph, "IdeaGraphState"))
        self.assertTrue(hasattr(idea_graph, "IdeaGraphNode"))
        self.assertTrue(hasattr(idea_graph, "IdeaGraphNodes"))
        self.assertTrue(hasattr(idea_graph, "build_idea_graph"))
        self.assertIn("IdeaGraphNode", workflows.__all__)
        self.assertIn("IdeaGraphNodes", workflows.__all__)
        self.assertIn("IdeaGraphState", workflows.__all__)
        self.assertIn("build_idea_graph", workflows.__all__)

    def test_build_idea_graph_runs_nodes_in_phase_8b_order(self):
        calls = []

        def make_node(name: str, update: dict):
            def node(state: dict) -> dict:
                calls.append(name)
                return update

            return node

        graph = build_idea_graph(
            IdeaGraphNodes(
                load_sources=make_node("load_sources", {"papers": ["paper-1"]}),
                ensure_breakdowns=make_node(
                    "ensure_breakdowns",
                    {"paper_contexts": [{"paper": "paper-1"}]},
                ),
                normalize_context=make_node(
                    "normalize_context",
                    {
                        "selected_papers": [{"id": "paper-1"}],
                        "source_topic": "retrieval",
                        "idea_context": {"papers": [{"title": "paper-1"}]},
                    },
                ),
                generate_candidates=make_node(
                    "generate_candidates",
                    {"candidate_ideas": [{"title": "candidate"}]},
                ),
                critique_and_filter=make_node(
                    "critique_and_filter",
                    {"ideas": [{"title": "idea"}]},
                ),
                build_response=make_node(
                    "build_response",
                    {
                        "warnings": ["warning"],
                    },
                ),
            )
        )

        result = graph.invoke({"paper_ids": []})

        self.assertEqual(
            calls,
            [
                "load_sources",
                "ensure_breakdowns",
                "normalize_context",
                "generate_candidates",
                "critique_and_filter",
                "build_response",
            ],
        )
        self.assertEqual(result["papers"], ["paper-1"])
        self.assertEqual(result["paper_contexts"], [{"paper": "paper-1"}])
        self.assertEqual(result["selected_papers"], [{"id": "paper-1"}])
        self.assertEqual(result["source_topic"], "retrieval")
        self.assertEqual(result["idea_context"], {"papers": [{"title": "paper-1"}]})
        self.assertEqual(result["candidate_ideas"], [{"title": "candidate"}])
        self.assertEqual(result["ideas"], [{"title": "idea"}])
        self.assertEqual(result["warnings"], ["warning"])

    def test_build_idea_graph_preserves_required_state_fields(self):
        user_id = uuid.uuid4()
        paper_id = uuid.uuid4()
        db = object()

        def pass_through_node(state: dict) -> dict:
            return {}

        graph = build_idea_graph(
            IdeaGraphNodes(
                load_sources=pass_through_node,
                ensure_breakdowns=pass_through_node,
                normalize_context=pass_through_node,
                generate_candidates=pass_through_node,
                critique_and_filter=pass_through_node,
                build_response=pass_through_node,
            )
        )

        result = graph.invoke({
            "db": db,
            "user_id": user_id,
            "paper_ids": [paper_id],
            "topic": "long-context retrieval",
        })

        self.assertIs(result["db"], db)
        self.assertEqual(result["user_id"], user_id)
        self.assertEqual(result["paper_ids"], [paper_id])
        self.assertEqual(result["topic"], "long-context retrieval")


class IdeaGraphServiceIntegrationTests(unittest.TestCase):
    def test_generate_paper_ideas_invokes_graph_after_validation_with_normalized_state(self):
        db = object()
        user_id = uuid.uuid4()
        paper_ids = [uuid.uuid4(), uuid.uuid4()]
        expected_response = {
            "selected_papers": [{"id": str(paper_ids[0])}],
            "source_topic": "long-context retrieval",
            "ideas": [{"title": "idea"}],
            "warnings": ["warning"],
        }
        graph = Mock()
        graph.invoke.return_value = expected_response

        with patch(
            "app.services.paper_ideas.build_idea_graph",
            return_value=graph,
        ) as mock_build_graph:
            result = generate_paper_ideas(
                db=db,
                user_id=user_id,
                paper_ids=[f" {paper_id} " for paper_id in paper_ids],
                topic="  long-context retrieval  ",
            )

        self.assertEqual(result, expected_response)
        mock_build_graph.assert_called_once()
        self.assertIsInstance(mock_build_graph.call_args.args[0], IdeaGraphNodes)
        graph.invoke.assert_called_once()
        initial_state = graph.invoke.call_args.args[0]
        self.assertIs(initial_state["db"], db)
        self.assertEqual(initial_state["user_id"], user_id)
        self.assertEqual(initial_state["paper_ids"], paper_ids)
        self.assertEqual(initial_state["topic"], "long-context retrieval")

    def test_generate_paper_ideas_does_not_build_graph_when_validation_fails(self):
        with patch("app.services.paper_ideas.build_idea_graph") as mock_build_graph:
            with self.assertRaises(HTTPException):
                generate_paper_ideas(
                    db=object(),
                    user_id=uuid.uuid4(),
                    paper_ids=[],
                    topic="   ",
                )

        mock_build_graph.assert_not_called()


if __name__ == "__main__":
    unittest.main()
