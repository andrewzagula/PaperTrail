import importlib
import unittest
import uuid
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.services.paper_compare import compare_papers

from app.workflows.compare_graph import (
    CompareGraphNodes,
    build_compare_graph,
)


class CompareGraphFoundationTests(unittest.TestCase):
    def test_compare_graph_module_imports_and_exports_foundation_symbols(self):
        compare_graph = importlib.import_module("app.workflows.compare_graph")
        workflows = importlib.import_module("app.workflows")

        self.assertTrue(hasattr(compare_graph, "CompareGraphState"))
        self.assertTrue(hasattr(compare_graph, "CompareGraphNode"))
        self.assertTrue(hasattr(compare_graph, "CompareGraphNodes"))
        self.assertTrue(hasattr(compare_graph, "build_compare_graph"))
        self.assertEqual(
            workflows.__all__,
            [
                "CompareGraphNode",
                "CompareGraphNodes",
                "CompareGraphState",
                "IdeaGraphNode",
                "IdeaGraphNodes",
                "IdeaGraphState",
                "ImplementationGraphNode",
                "ImplementationGraphNodes",
                "ImplementationGraphState",
                "build_compare_graph",
                "build_idea_graph",
                "build_implementation_graph",
            ],
        )

    def test_build_compare_graph_runs_nodes_in_phase_7_order(self):
        calls = []

        def make_node(name: str, update: dict):
            def node(state: dict) -> dict:
                calls.append(name)
                return update

            return node

        graph = build_compare_graph(
            CompareGraphNodes(
                load_papers=make_node("load_papers", {"papers": ["paper-1"]}),
                ensure_breakdowns=make_node(
                    "ensure_breakdowns",
                    {"warnings": ["breakdown warning"]},
                ),
                normalize_profiles=make_node(
                    "normalize_profiles",
                    {"normalized_profiles": [{"paper_id": "paper-1"}]},
                ),
                synthesize_narrative=make_node(
                    "synthesize_narrative",
                    {"narrative_summary": "summary"},
                ),
                build_response=make_node(
                    "build_response",
                    {
                        "selected_papers": [{"id": "paper-1"}],
                        "comparison_table": {"rows": []},
                    },
                ),
            )
        )

        result = graph.invoke({"paper_ids": []})

        self.assertEqual(
            calls,
            [
                "load_papers",
                "ensure_breakdowns",
                "normalize_profiles",
                "synthesize_narrative",
                "build_response",
            ],
        )
        self.assertEqual(result["papers"], ["paper-1"])
        self.assertEqual(result["warnings"], ["breakdown warning"])
        self.assertEqual(result["normalized_profiles"], [{"paper_id": "paper-1"}])
        self.assertEqual(result["narrative_summary"], "summary")
        self.assertEqual(result["selected_papers"], [{"id": "paper-1"}])
        self.assertEqual(result["comparison_table"], {"rows": []})

    def test_build_compare_graph_preserves_required_state_fields(self):
        user_id = uuid.uuid4()
        paper_id = uuid.uuid4()
        db = object()

        def pass_through_node(state: dict) -> dict:
            return {}

        graph = build_compare_graph(
            CompareGraphNodes(
                load_papers=pass_through_node,
                ensure_breakdowns=pass_through_node,
                normalize_profiles=pass_through_node,
                synthesize_narrative=pass_through_node,
                build_response=pass_through_node,
            )
        )

        result = graph.invoke({
            "db": db,
            "user_id": user_id,
            "paper_ids": [paper_id],
        })

        self.assertIs(result["db"], db)
        self.assertEqual(result["user_id"], user_id)
        self.assertEqual(result["paper_ids"], [paper_id])


class CompareGraphServiceIntegrationTests(unittest.TestCase):
    def test_compare_papers_invokes_graph_after_validation_with_normalized_ids(self):
        db = object()
        user_id = uuid.uuid4()
        paper_ids = [uuid.uuid4(), uuid.uuid4()]
        expected_response = {
            "selected_papers": [{"id": str(paper_ids[0])}],
            "normalized_profiles": [{"paper_id": str(paper_ids[0])}],
            "comparison_table": {"columns": [], "rows": []},
            "narrative_summary": "summary",
            "warnings": ["warning"],
        }
        graph = Mock()
        graph.invoke.return_value = expected_response

        with patch(
            "app.services.paper_compare.build_compare_graph",
            return_value=graph,
        ) as mock_build_graph:
            result = compare_papers(
                db=db,
                user_id=user_id,
                paper_ids=[str(paper_id) for paper_id in paper_ids],
            )

        self.assertEqual(result, expected_response)
        mock_build_graph.assert_called_once()
        self.assertIsInstance(mock_build_graph.call_args.args[0], CompareGraphNodes)
        graph.invoke.assert_called_once()
        initial_state = graph.invoke.call_args.args[0]
        self.assertIs(initial_state["db"], db)
        self.assertEqual(initial_state["user_id"], user_id)
        self.assertEqual(initial_state["paper_ids"], paper_ids)

    def test_compare_papers_does_not_build_graph_when_validation_fails(self):
        with patch("app.services.paper_compare.build_compare_graph") as mock_build_graph:
            with self.assertRaises(HTTPException):
                compare_papers(
                    db=object(),
                    user_id=uuid.uuid4(),
                    paper_ids=[str(uuid.uuid4())],
                )

        mock_build_graph.assert_not_called()


if __name__ == "__main__":
    unittest.main()
