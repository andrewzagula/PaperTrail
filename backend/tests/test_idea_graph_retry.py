import unittest
from unittest.mock import patch

from app.services.paper_ideas import (
    CANDIDATE_GENERATION_FALLBACK_WARNING,
    INSUFFICIENT_FINAL_IDEAS_WARNING,
    MAX_CANDIDATE_GENERATION_ATTEMPTS,
    MIN_FINAL_IDEAS,
    _idea_graph_build_response,
    _idea_graph_should_retry_candidates,
)
from app.workflows.idea_graph import IdeaGraphNodes, build_idea_graph


def _ideas(count: int) -> list[dict]:
    return [{"title": f"idea-{i}"} for i in range(count)]


class ShouldRetryCandidatesTests(unittest.TestCase):
    """The policy that decides whether a second candidate pass is worthwhile."""

    def test_accepts_when_enough_ideas_survived(self):
        state = {"ideas": _ideas(MIN_FINAL_IDEAS), "generation_attempts": 1}
        self.assertFalse(_idea_graph_should_retry_candidates(state))

    def test_retries_when_too_few_ideas_survived(self):
        state = {"ideas": _ideas(MIN_FINAL_IDEAS - 1), "generation_attempts": 1}
        self.assertTrue(_idea_graph_should_retry_candidates(state))

    def test_does_not_retry_deterministic_candidates(self):
        """Templates regenerate identically, so a retry would burn a call for nothing."""
        state = {
            "ideas": _ideas(0),
            "generation_attempts": 1,
            "used_deterministic_candidates": True,
        }
        self.assertFalse(_idea_graph_should_retry_candidates(state))

    def test_stops_at_the_attempt_cap(self):
        state = {
            "ideas": _ideas(0),
            "generation_attempts": MAX_CANDIDATE_GENERATION_ATTEMPTS,
        }
        self.assertFalse(_idea_graph_should_retry_candidates(state))

    def test_does_not_retry_before_a_real_generation_pass(self):
        """Guards stubbed graphs that never record an attempt."""
        state = {"ideas": _ideas(0), "generation_attempts": 0}
        self.assertFalse(_idea_graph_should_retry_candidates(state))


class BuildResponseWarningTests(unittest.TestCase):
    def test_warns_only_when_the_final_result_is_short(self):
        result = _idea_graph_build_response({"ideas": _ideas(1), "warnings": []})
        self.assertIn(INSUFFICIENT_FINAL_IDEAS_WARNING, result["warnings"])

    def test_no_warning_when_enough_ideas(self):
        result = _idea_graph_build_response(
            {"ideas": _ideas(MIN_FINAL_IDEAS), "warnings": []}
        )
        self.assertNotIn(INSUFFICIENT_FINAL_IDEAS_WARNING, result["warnings"])

    def test_a_recovered_retry_does_not_claim_insufficient_ideas(self):
        """Regression: the warning must not leak from a discarded first pass."""
        result = _idea_graph_build_response(
            {"ideas": _ideas(MIN_FINAL_IDEAS), "warnings": []}
        )
        self.assertEqual(result["warnings"], [])


class IdeaGraphLoopTests(unittest.TestCase):
    """The compiled graph must actually route back through generate_candidates."""

    def _run(self, critique_results: list[list[dict]]):
        calls = []
        pending = list(critique_results)

        def generate(state):
            calls.append("generate")
            return {"generation_attempts": state.get("generation_attempts", 0) + 1}

        def critique(state):
            calls.append("critique")
            return {"ideas": pending.pop(0)}

        def build(state):
            calls.append("build")
            return {"ideas": state.get("ideas", [])}

        def passthrough(state):
            return {}

        graph = build_idea_graph(
            IdeaGraphNodes(
                load_sources=passthrough,
                ensure_breakdowns=passthrough,
                normalize_context=passthrough,
                generate_candidates=generate,
                critique_and_filter=critique,
                build_response=build,
                should_retry_candidates=_idea_graph_should_retry_candidates,
            )
        )
        result = graph.invoke({"paper_ids": []})
        return calls, result

    def test_loops_back_then_accepts_the_recovered_pass(self):
        calls, result = self._run([_ideas(1), _ideas(MIN_FINAL_IDEAS)])

        self.assertEqual(
            calls,
            ["generate", "critique", "generate", "critique", "build"],
        )
        self.assertEqual(len(result["ideas"]), MIN_FINAL_IDEAS)

    def test_single_pass_when_first_attempt_is_good(self):
        calls, _ = self._run([_ideas(MIN_FINAL_IDEAS)])
        self.assertEqual(calls, ["generate", "critique", "build"])

    def test_terminates_at_the_cap_when_retries_keep_failing(self):
        calls, result = self._run([_ideas(1)] * MAX_CANDIDATE_GENERATION_ATTEMPTS)

        self.assertEqual(calls.count("generate"), MAX_CANDIDATE_GENERATION_ATTEMPTS)
        self.assertEqual(calls[-1], "build")
        self.assertLess(len(result["ideas"]), MIN_FINAL_IDEAS)


class RetryPromptTests(unittest.TestCase):
    def test_retry_attempt_asks_for_more_distinct_candidates(self):
        from app.services.paper_ideas import generate_candidate_ideas

        with patch(
            "app.services.paper_ideas._request_structured_json",
            return_value={},
        ) as mock_request:
            generate_candidate_ideas({"papers": []}, attempt=1)
            first_prompt = mock_request.call_args.kwargs["messages"][0]["content"]

            generate_candidate_ideas({"papers": []}, attempt=2)
            retry_prompt = mock_request.call_args.kwargs["messages"][0]["content"]

        self.assertNotIn("previous attempt", first_prompt)
        self.assertIn("previous attempt", retry_prompt)
        self.assertGreater(len(retry_prompt), len(first_prompt))


class DeterministicFallbackLoopTests(unittest.TestCase):
    def test_deterministic_candidates_end_the_run_without_retrying(self):
        calls = []

        def generate(state):
            calls.append("generate")
            return {
                "generation_attempts": state.get("generation_attempts", 0) + 1,
                "used_deterministic_candidates": True,
                "warnings": [CANDIDATE_GENERATION_FALLBACK_WARNING],
            }

        def critique(state):
            calls.append("critique")
            return {"ideas": _ideas(1)}

        def passthrough(state):
            return {}

        graph = build_idea_graph(
            IdeaGraphNodes(
                load_sources=passthrough,
                ensure_breakdowns=passthrough,
                normalize_context=passthrough,
                generate_candidates=generate,
                critique_and_filter=critique,
                build_response=_idea_graph_build_response,
                should_retry_candidates=_idea_graph_should_retry_candidates,
            )
        )
        result = graph.invoke({"paper_ids": []})

        self.assertEqual(calls, ["generate", "critique"])
        self.assertIn(CANDIDATE_GENERATION_FALLBACK_WARNING, result["warnings"])
        self.assertIn(INSUFFICIENT_FINAL_IDEAS_WARNING, result["warnings"])


if __name__ == "__main__":
    unittest.main()
