import unittest
from unittest.mock import patch

from app.services.paper_implementation import (
    MAX_STARTER_CODE_ATTEMPTS,
    _build_unsafe_code_correction,
    _implementation_graph_build_response,
    _implementation_graph_should_regenerate_starter_code,
)
from app.workflows.implementation_graph import (
    ImplementationGraphNodes,
    build_implementation_graph,
)

UNSAFE = [{"path": "data.py", "reasons": ["network calls"]}]


class ShouldRegenerateStarterCodeTests(unittest.TestCase):
    """The policy deciding whether rejected code is worth regenerating."""

    def test_accepts_when_review_found_nothing_unsafe(self):
        state = {"unsafe_code_feedback": [], "code_generation_attempts": 1}
        self.assertFalse(_implementation_graph_should_regenerate_starter_code(state))

    def test_regenerates_when_review_stripped_unsafe_code(self):
        state = {"unsafe_code_feedback": UNSAFE, "code_generation_attempts": 1}
        self.assertTrue(_implementation_graph_should_regenerate_starter_code(state))

    def test_does_not_regenerate_deterministic_scaffolds(self):
        """Templates are safe by construction; regenerating burns a call."""
        state = {
            "unsafe_code_feedback": UNSAFE,
            "code_generation_attempts": 1,
            "used_deterministic_starter_code": True,
        }
        self.assertFalse(_implementation_graph_should_regenerate_starter_code(state))

    def test_stops_at_the_attempt_cap(self):
        state = {
            "unsafe_code_feedback": UNSAFE,
            "code_generation_attempts": MAX_STARTER_CODE_ATTEMPTS,
        }
        self.assertFalse(_implementation_graph_should_regenerate_starter_code(state))

    def test_does_not_regenerate_before_a_real_pass(self):
        state = {"unsafe_code_feedback": UNSAFE, "code_generation_attempts": 0}
        self.assertFalse(_implementation_graph_should_regenerate_starter_code(state))


class UnsafeCodeCorrectionTests(unittest.TestCase):
    def test_no_directive_without_feedback(self):
        self.assertEqual(_build_unsafe_code_correction([]), "")

    def test_directive_names_the_rejected_paths_and_reasons(self):
        directive = _build_unsafe_code_correction(
            [{"path": "data.py", "reasons": ["network calls", "dataset downloads"]}]
        )
        self.assertIn("data.py", directive)
        self.assertIn("network calls", directive)
        self.assertIn("dataset downloads", directive)


class ReviewWarningHygieneTests(unittest.TestCase):
    def test_build_response_merges_review_warnings(self):
        result = _implementation_graph_build_response({
            "paper": _FakePaper(),
            "target_framework": "pytorch",
            "warnings": ["earlier stage warning"],
            "review_warnings": ["data.py was replaced"],
        })
        self.assertIn("earlier stage warning", result["warnings"])
        self.assertIn("data.py was replaced", result["warnings"])

    def test_a_clean_regeneration_drops_the_previous_replacement_note(self):
        """Regression: review_warnings are per-pass, so a clean retry stays clean."""
        result = _implementation_graph_build_response({
            "paper": _FakePaper(),
            "target_framework": "pytorch",
            "warnings": [],
            "review_warnings": [],
        })
        self.assertEqual(result["warnings"], [])


class ImplementationGraphLoopTests(unittest.TestCase):
    def _run(self, review_results: list[list[dict]]):
        calls = []
        pending = list(review_results)

        def generate(state):
            calls.append("generate")
            return {
                "code_generation_attempts": state.get("code_generation_attempts", 0) + 1
            }

        def review(state):
            calls.append("review")
            return {"unsafe_code_feedback": pending.pop(0)}

        def build(state):
            calls.append("build")
            return {"starter_code": state.get("starter_code") or []}

        def passthrough(state):
            return {}

        graph = build_implementation_graph(
            ImplementationGraphNodes(
                load_paper=passthrough,
                prepare_context=passthrough,
                extract_algorithm=passthrough,
                analyze_gaps=passthrough,
                generate_pseudocode=passthrough,
                generate_starter_code=generate,
                review_scaffold=review,
                build_response=build,
                should_regenerate_starter_code=(
                    _implementation_graph_should_regenerate_starter_code
                ),
            )
        )
        graph.invoke({"target_framework": "pytorch"})
        return calls

    def test_regenerates_once_then_accepts_the_clean_pass(self):
        calls = self._run([UNSAFE, []])
        self.assertEqual(
            calls, ["generate", "review", "generate", "review", "build"]
        )

    def test_single_pass_when_first_attempt_is_clean(self):
        calls = self._run([[]])
        self.assertEqual(calls, ["generate", "review", "build"])

    def test_terminates_at_the_cap_when_code_stays_unsafe(self):
        calls = self._run([UNSAFE] * MAX_STARTER_CODE_ATTEMPTS)
        self.assertEqual(calls.count("generate"), MAX_STARTER_CODE_ATTEMPTS)
        self.assertEqual(calls[-1], "build")


class StarterCodePromptFeedbackTests(unittest.TestCase):
    def test_regeneration_prompt_carries_the_rejection_reasons(self):
        from app.services.paper_implementation import (
            generate_implementation_starter_code,
        )

        class _Client:
            def __init__(self):
                self.messages = None

            def generate_structured(self, **kwargs):
                self.messages = kwargs["messages"]
                return {}

        client = _Client()
        with patch(
            "app.services.paper_implementation.get_structured_client",
            return_value=client,
        ):
            generate_implementation_starter_code(
                implementation_context={},
                algorithm_steps=[],
                assumptions_and_gaps=[],
                pseudocode="",
                focus=None,
                target_language="python",
                target_framework="pytorch",
            )
            first = client.messages[0]["content"]

            generate_implementation_starter_code(
                implementation_context={},
                algorithm_steps=[],
                assumptions_and_gaps=[],
                pseudocode="",
                focus=None,
                target_language="python",
                target_framework="pytorch",
                unsafe_feedback=UNSAFE,
            )
            retry = client.messages[0]["content"]

        self.assertNotIn("rejected by the safety review", first)
        self.assertIn("rejected by the safety review", retry)
        self.assertIn("data.py", retry)


class _FakePaper:
    id = "00000000-0000-0000-0000-000000000000"
    title = "Paper"
    authors = None
    arxiv_url = None
    created_at = None


if __name__ == "__main__":
    unittest.main()
