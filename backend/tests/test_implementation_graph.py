import importlib
import unittest
import uuid
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.services.paper_implementation import generate_paper_implementation
from app.workflows.implementation_graph import (
    ImplementationGraphNodes,
    build_implementation_graph,
)


class ImplementationGraphFoundationTests(unittest.TestCase):
    def test_implementation_graph_module_imports_and_exports_foundation_symbols(self):
        implementation_graph = importlib.import_module(
            "app.workflows.implementation_graph"
        )
        workflows = importlib.import_module("app.workflows")

        self.assertTrue(hasattr(implementation_graph, "ImplementationGraphState"))
        self.assertTrue(hasattr(implementation_graph, "ImplementationGraphNode"))
        self.assertTrue(hasattr(implementation_graph, "ImplementationGraphNodes"))
        self.assertTrue(hasattr(implementation_graph, "build_implementation_graph"))
        self.assertIn("ImplementationGraphNode", workflows.__all__)
        self.assertIn("ImplementationGraphNodes", workflows.__all__)
        self.assertIn("ImplementationGraphState", workflows.__all__)
        self.assertIn("build_implementation_graph", workflows.__all__)

    def test_build_implementation_graph_runs_nodes_in_phase_9a_order(self):
        calls = []

        def make_node(name: str, update: dict):
            def node(state: dict) -> dict:
                calls.append(name)
                return update

            return node

        graph = build_implementation_graph(
            ImplementationGraphNodes(
                load_paper=make_node("load_paper", {"paper": "paper-1"}),
                prepare_context=make_node(
                    "prepare_context",
                    {"source_sections": [{"title": "Method"}]},
                ),
                extract_algorithm=make_node(
                    "extract_algorithm",
                    {"algorithm_steps": [{"title": "step"}]},
                ),
                analyze_gaps=make_node(
                    "analyze_gaps",
                    {"assumptions_and_gaps": [{"category": "data"}]},
                ),
                generate_pseudocode=make_node(
                    "generate_pseudocode",
                    {"pseudocode": "setup"},
                ),
                generate_starter_code=make_node(
                    "generate_starter_code",
                    {"starter_code": [{"path": "model.py"}]},
                ),
                review_scaffold=make_node(
                    "review_scaffold",
                    {"warnings": ["warning"]},
                ),
                build_response=make_node(
                    "build_response",
                    {
                        "implementation_summary": "summary",
                        "setup_notes": ["setup note"],
                        "test_plan": ["test"],
                    },
                ),
            )
        )

        result = graph.invoke({"paper_id": uuid.uuid4()})

        self.assertEqual(
            calls,
            [
                "load_paper",
                "prepare_context",
                "extract_algorithm",
                "analyze_gaps",
                "generate_pseudocode",
                "generate_starter_code",
                "review_scaffold",
                "build_response",
            ],
        )
        self.assertEqual(result["paper"], "paper-1")
        self.assertEqual(result["source_sections"], [{"title": "Method"}])
        self.assertEqual(result["algorithm_steps"], [{"title": "step"}])
        self.assertEqual(result["assumptions_and_gaps"], [{"category": "data"}])
        self.assertEqual(result["pseudocode"], "setup")
        self.assertEqual(result["starter_code"], [{"path": "model.py"}])
        self.assertEqual(result["warnings"], ["warning"])
        self.assertEqual(result["implementation_summary"], "summary")
        self.assertEqual(result["setup_notes"], ["setup note"])
        self.assertEqual(result["test_plan"], ["test"])

    def test_build_implementation_graph_preserves_required_state_fields(self):
        user_id = uuid.uuid4()
        paper_id = uuid.uuid4()
        db = object()

        def pass_through_node(state: dict) -> dict:
            return {}

        graph = build_implementation_graph(
            ImplementationGraphNodes(
                load_paper=pass_through_node,
                prepare_context=pass_through_node,
                extract_algorithm=pass_through_node,
                analyze_gaps=pass_through_node,
                generate_pseudocode=pass_through_node,
                generate_starter_code=pass_through_node,
                review_scaffold=pass_through_node,
                build_response=pass_through_node,
            )
        )

        result = graph.invoke({
            "db": db,
            "user_id": user_id,
            "paper_id": paper_id,
            "focus": "training loop",
            "target_language": "python",
            "target_framework": "pytorch",
        })

        self.assertIs(result["db"], db)
        self.assertEqual(result["user_id"], user_id)
        self.assertEqual(result["paper_id"], paper_id)
        self.assertEqual(result["focus"], "training loop")
        self.assertEqual(result["target_language"], "python")
        self.assertEqual(result["target_framework"], "pytorch")


class ImplementationGraphServiceIntegrationTests(unittest.TestCase):
    def test_generate_paper_implementation_invokes_graph_after_validation(self):
        db = object()
        user_id = uuid.uuid4()
        paper_id = uuid.uuid4()
        expected_response = {
            "paper": {"id": str(paper_id), "title": "Paper"},
            "source_sections": [],
            "implementation_summary": "summary",
            "algorithm_steps": [],
            "assumptions_and_gaps": [],
            "pseudocode": "",
            "starter_code": [],
            "setup_notes": [],
            "test_plan": [],
            "warnings": ["warning"],
        }
        graph = Mock()
        graph.invoke.return_value = expected_response

        with patch(
            "app.services.paper_implementation.build_implementation_graph",
            return_value=graph,
        ) as mock_build_graph:
            result = generate_paper_implementation(
                db=db,
                user_id=user_id,
                paper_id=f" {paper_id} ",
                focus="  training loop  ",
                target_language=" python ",
                target_framework=" pytorch ",
            )

        self.assertEqual(result, expected_response)
        mock_build_graph.assert_called_once()
        self.assertIsInstance(mock_build_graph.call_args.args[0], ImplementationGraphNodes)
        graph.invoke.assert_called_once()
        initial_state = graph.invoke.call_args.args[0]
        self.assertIs(initial_state["db"], db)
        self.assertEqual(initial_state["user_id"], user_id)
        self.assertEqual(initial_state["paper_id"], paper_id)
        self.assertEqual(initial_state["focus"], "training loop")
        self.assertEqual(initial_state["target_language"], "python")
        self.assertEqual(initial_state["target_framework"], "pytorch")

    def test_generate_paper_implementation_does_not_build_graph_when_validation_fails(
        self,
    ):
        with patch(
            "app.services.paper_implementation.build_implementation_graph"
        ) as mock_build_graph:
            with self.assertRaises(HTTPException):
                generate_paper_implementation(
                    db=object(),
                    user_id=uuid.uuid4(),
                    paper_id="not-a-uuid",
                )

        mock_build_graph.assert_not_called()


if __name__ == "__main__":
    unittest.main()
