import unittest

from app.workflows.compare_graph import (
    CompareGraphNodes,
    build_compare_graph,
)

from app.services.paper_compare import (
    COMPARE_FIELDS,
    MAX_WIDENED_COMPARE_SECTIONS,
    NOT_EXPLICITLY_DISCUSSED,
    _compare_profile_is_sparse,
    WIDENED_COMPARE_CONTEXT_WARNING,
    _compare_graph_should_widen_context,
    _compare_graph_widen_context,
    _build_section_context,
    _compare_graph_normalize_profiles,
    _select_relevant_sections,
    _select_substantive_compare_sections,
    compare_papers,
)
from unittest.mock import patch


class _FakePaper:
    id = "00000000-0000-0000-0000-000000000000"
    title = "Paper"
    authors = None
    abstract = None
    arxiv_url = None
    created_at = None


class _Section:
    def __init__(self, order: int, title: str, content: str):
        self.id = f"section-{order}"
        self.section_order = order
        self.section_title = title
        self.content = content


def _profile(sentinel_fields: int) -> dict:
    """A compare profile with `sentinel_fields` of its six fields missing."""
    profile = {"paper_id": "paper-1", "title": "Paper", "warnings": []}
    for index, field in enumerate(COMPARE_FIELDS):
        profile[field] = (
            NOT_EXPLICITLY_DISCUSSED if index < sentinel_fields else f"real {field}"
        )
    return profile


class CompareProfileIsSparseTests(unittest.TestCase):
    def test_sparse_when_four_of_six_fields_are_sentinels(self):
        self.assertTrue(_compare_profile_is_sparse(_profile(4)))

    def test_not_sparse_at_three_of_six(self):
        self.assertFalse(_compare_profile_is_sparse(_profile(3)))

    def test_not_sparse_when_every_field_is_present(self):
        self.assertFalse(_compare_profile_is_sparse(_profile(0)))

    def test_sparse_when_every_field_is_missing(self):
        self.assertTrue(_compare_profile_is_sparse(_profile(6)))


class SelectSubstantiveCompareSectionsTests(unittest.TestCase):
    """The title-independent strategy used when a profile comes back sparse."""

    def test_prefers_the_longest_sections(self):
        sections = [
            _Section(0, "Preamble", "x"),
            _Section(1, "Unlabelled", "y" * 5000),
            _Section(2, "Notes", "z" * 10),
        ]
        picked = _select_substantive_compare_sections(sections)
        self.assertIn("Unlabelled", [s.section_title for s in picked])

    def test_restores_reading_order(self):
        sections = [
            _Section(0, "First", "a" * 100),
            _Section(1, "Second", "b" * 9000),
            _Section(2, "Third", "c" * 500),
        ]
        picked = _select_substantive_compare_sections(sections)
        self.assertEqual([s.section_order for s in picked], [0, 1, 2])

    def test_caps_at_the_widened_section_limit(self):
        sections = [_Section(i, f"S{i}", "x" * (100 * (i + 1))) for i in range(20)]
        self.assertEqual(
            len(_select_substantive_compare_sections(sections)),
            MAX_WIDENED_COMPARE_SECTIONS,
        )

    def test_skips_empty_sections(self):
        sections = [_Section(0, "Empty", "   "), _Section(1, "Real", "content")]
        picked = _select_substantive_compare_sections(sections)
        self.assertEqual([s.section_title for s in picked], ["Real"])

    def test_returns_nothing_when_no_section_has_content(self):
        self.assertEqual(_select_substantive_compare_sections([_Section(0, "E", "")]), [])

    def test_differs_from_title_based_selection(self):
        """Otherwise widening would re-run the same strategy and change nothing."""
        sections = [_Section(i, f"S{i}", "x" * (100 * (i + 1))) for i in range(12)]
        title_based = [s.section_order for s in _select_relevant_sections(sections)]
        substantive = [
            s.section_order for s in _select_substantive_compare_sections(sections)
        ]
        self.assertNotEqual(title_based, substantive)


def _wide_sections() -> list:
    """Sections where title-based and substantive selection genuinely differ."""
    return [_Section(i, f"S{i}", "x" * (100 * (i + 1))) for i in range(12)]


def _state(sentinel_fields: int, *, widened: bool = False) -> dict:
    return {
        "paper_contexts": [
            {
                "paper": object(),
                "sections": _wide_sections(),
                "breakdown": {},
                "breakdown_warnings": [],
                "widened": widened,
            }
        ],
        "normalized_profiles": [_profile(sentinel_fields)],
    }


class ShouldWidenCompareContextTests(unittest.TestCase):
    def test_widens_when_a_profile_is_sparse(self):
        self.assertTrue(_compare_graph_should_widen_context(_state(4)))

    def test_does_not_widen_when_profiles_are_usable(self):
        self.assertFalse(_compare_graph_should_widen_context(_state(3)))

    def test_does_not_widen_the_same_paper_twice(self):
        self.assertFalse(_compare_graph_should_widen_context(_state(6, widened=True)))

    def test_does_not_widen_when_selection_would_not_change(self):
        """A short paper selects the same sections either way, so retrying is waste."""
        state = _state(6)
        state["paper_contexts"][0]["sections"] = [_Section(0, "Only", "content")]
        self.assertFalse(_compare_graph_should_widen_context(state))

    def test_does_not_widen_before_profiles_exist(self):
        state = _state(6)
        state["normalized_profiles"] = []
        self.assertFalse(_compare_graph_should_widen_context(state))


class WidenCompareContextTests(unittest.TestCase):
    def test_replaces_sections_with_the_substantive_selection(self):
        state = _state(4)
        widened = _compare_graph_widen_context(state)["paper_contexts"][0]
        self.assertEqual(
            [s.section_order for s in widened["sections"]],
            [s.section_order for s in _select_substantive_compare_sections(_wide_sections())],
        )

    def test_marks_the_paper_widened_and_preselected(self):
        state = _state(4)
        widened = _compare_graph_widen_context(state)["paper_contexts"][0]
        self.assertTrue(widened["widened"])
        self.assertTrue(widened["preselected"])

    def test_seeds_a_warning_so_the_degradation_reaches_the_user(self):
        state = _state(4)
        widened = _compare_graph_widen_context(state)["paper_contexts"][0]
        self.assertIn(WIDENED_COMPARE_CONTEXT_WARNING, widened["breakdown_warnings"])

    def test_leaves_usable_papers_untouched(self):
        state = _state(3)
        original = state["paper_contexts"][0]["sections"]
        widened = _compare_graph_widen_context(state)["paper_contexts"][0]
        self.assertIs(widened["sections"], original)
        self.assertFalse(widened.get("widened"))


class CompareGraphWiringTests(unittest.TestCase):
    """The back-edge: widening happens after profiling, then profiles again."""

    def _nodes(self, calls: list, *, widen_until: int):
        state = {"passes": 0}

        def make(name: str, update=None):
            def node(_state: dict) -> dict:
                calls.append(name)
                return update or {}

            return node

        def normalize(_state: dict) -> dict:
            calls.append("normalize_profiles")
            state["passes"] += 1
            return {"normalized_profiles": [{"pass": state["passes"]}]}

        return CompareGraphNodes(
            load_papers=make("load_papers"),
            ensure_breakdowns=make("ensure_breakdowns"),
            normalize_profiles=normalize,
            synthesize_narrative=make("synthesize_narrative", {"narrative_summary": "s"}),
            build_response=make("build_response", {"comparison_table": {"rows": []}}),
            widen_context=make("widen_context"),
            should_widen_context=lambda _s: state["passes"] <= widen_until,
        )

    def test_defaults_keep_the_linear_path(self):
        calls = []

        def make(name: str):
            def node(_state: dict) -> dict:
                calls.append(name)
                return {}

            return node

        graph = build_compare_graph(
            CompareGraphNodes(
                load_papers=make("load_papers"),
                ensure_breakdowns=make("ensure_breakdowns"),
                normalize_profiles=make("normalize_profiles"),
                synthesize_narrative=make("synthesize_narrative"),
                build_response=make("build_response"),
            )
        )
        graph.invoke({"paper_ids": []})

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

    def test_widening_loops_back_through_normalize_profiles(self):
        calls = []
        graph = build_compare_graph(self._nodes(calls, widen_until=1))
        graph.invoke({"paper_ids": []})

        self.assertEqual(
            calls,
            [
                "load_papers",
                "ensure_breakdowns",
                "normalize_profiles",
                "widen_context",
                "normalize_profiles",
                "synthesize_narrative",
                "build_response",
            ],
        )

    def test_skips_widening_when_the_decision_declines(self):
        calls = []
        graph = build_compare_graph(self._nodes(calls, widen_until=0))
        graph.invoke({"paper_ids": []})

        self.assertNotIn("widen_context", calls)
        self.assertEqual(calls.count("normalize_profiles"), 1)


class PreselectedSectionContextTests(unittest.TestCase):
    """Widened sections must not be re-filtered by the title-based selector."""

    def test_preselected_keeps_sections_title_selection_would_drop(self):
        sections = _wide_sections()
        dropped = [s for s in sections if s.section_order > 2]
        self.assertTrue(dropped, "fixture must contain sections title selection drops")

        context = _build_section_context(sections, preselected=True)

        for section in dropped:
            self.assertIn(section.section_title, context)

    def test_default_still_applies_title_based_selection(self):
        context = _build_section_context(_wide_sections())
        self.assertNotIn("S11", context)


class NormalizeProfilesThreadingTests(unittest.TestCase):
    def test_passes_preselected_from_the_paper_context(self):
        paper_context = {
            "paper": _FakePaper(),
            "sections": [],
            "breakdown": {},
            "breakdown_warnings": [],
            "preselected": True,
        }

        with patch(
            "app.services.paper_compare.normalize_paper_for_compare",
            return_value={},
        ) as normalize:
            _compare_graph_normalize_profiles({"paper_contexts": [paper_context]})

        self.assertTrue(normalize.call_args.kwargs["preselected"])


class CompareServiceWiringTests(unittest.TestCase):
    def test_compare_papers_wires_the_widen_node_and_decision(self):
        import uuid as _uuid

        graph = unittest.mock.Mock()
        graph.invoke.return_value = {
            "selected_papers": [],
            "normalized_profiles": [],
            "comparison_table": {},
            "narrative_summary": "",
            "warnings": [],
        }

        with patch(
            "app.services.paper_compare.build_compare_graph", return_value=graph
        ) as build:
            compare_papers(
                db=object(),
                user_id=_uuid.uuid4(),
                paper_ids=[str(_uuid.uuid4()), str(_uuid.uuid4())],
            )

        nodes = build.call_args.args[0]
        self.assertIs(nodes.widen_context, _compare_graph_widen_context)
        self.assertIs(nodes.should_widen_context, _compare_graph_should_widen_context)


class CycleTerminationTests(unittest.TestCase):
    """The pathological case: profiling never improves, however wide the context."""

    def test_terminates_when_profiles_stay_sparse_forever(self):
        passes = {"count": 0}

        def always_sparse(state: dict) -> dict:
            passes["count"] += 1
            return {"normalized_profiles": [_profile(6) for _ in state["paper_contexts"]]}

        def load_contexts(_state: dict) -> dict:
            return {
                "paper_contexts": [
                    {
                        "paper": _FakePaper(),
                        "sections": _wide_sections(),
                        "breakdown": {},
                        "breakdown_warnings": [],
                    }
                ]
            }

        graph = build_compare_graph(
            CompareGraphNodes(
                load_papers=lambda _s: {},
                ensure_breakdowns=load_contexts,
                normalize_profiles=always_sparse,
                synthesize_narrative=lambda _s: {"narrative_summary": ""},
                build_response=lambda _s: {"comparison_table": {}},
                widen_context=_compare_graph_widen_context,
                should_widen_context=_compare_graph_should_widen_context,
            )
        )

        graph.invoke({"paper_ids": []})

        # One initial profiling pass, one widened retry, then it gives up.
        self.assertEqual(passes["count"], 2)


if __name__ == "__main__":
    unittest.main()
