import unittest

from app.services.paper_implementation import (
    MAX_SOURCE_SECTIONS,
    WIDENED_METHOD_CONTEXT_WARNING,
    _implementation_graph_should_widen_context,
    _implementation_graph_widen_context,
    _select_substantive_sections,
)
from app.workflows.implementation_graph import (
    ImplementationGraphNodes,
    build_implementation_graph,
)


class _Section:
    def __init__(self, order: int, title: str, content: str):
        self.id = f"section-{order}"
        self.section_order = order
        self.section_title = title
        self.content = content


class _FakePaper:
    id = "00000000-0000-0000-0000-000000000000"
    title = "Paper"
    authors = None
    abstract = None
    arxiv_url = None
    created_at = None


class SelectSubstantiveSectionsTests(unittest.TestCase):
    """The title-independent strategy used when no method section is found."""

    def test_prefers_the_longest_sections(self):
        sections = [
            _Section(0, "Preamble", "x"),
            _Section(1, "Unlabelled", "y" * 5000),
            _Section(2, "Notes", "z" * 10),
        ]
        picked = _select_substantive_sections(sections)
        self.assertIn("Unlabelled", [s.section_title for s in picked])

    def test_restores_reading_order(self):
        sections = [
            _Section(0, "First", "a" * 100),
            _Section(1, "Second", "b" * 9000),
            _Section(2, "Third", "c" * 500),
        ]
        picked = _select_substantive_sections(sections)
        self.assertEqual([s.section_order for s in picked], [0, 1, 2])

    def test_caps_at_the_source_section_limit(self):
        sections = [_Section(i, f"S{i}", "x" * (100 * (i + 1))) for i in range(20)]
        self.assertEqual(
            len(_select_substantive_sections(sections)), MAX_SOURCE_SECTIONS
        )

    def test_skips_empty_sections(self):
        sections = [_Section(0, "Empty", "   "), _Section(1, "Real", "content")]
        picked = _select_substantive_sections(sections)
        self.assertEqual([s.section_title for s in picked], ["Real"])

    def test_returns_nothing_when_no_section_has_content(self):
        self.assertEqual(_select_substantive_sections([_Section(0, "E", "")]), [])

    def test_differs_from_title_based_selection(self):
        """Otherwise the branch would be a no-op re-run of the same strategy."""
        sections = [_Section(i, f"S{i}", "x" * (100 * (i + 1))) for i in range(12)]
        # Title-based selection falls through to the first N sections.
        title_based = list(range(MAX_SOURCE_SECTIONS))
        substantive = [s.section_order for s in _select_substantive_sections(sections)]
        self.assertNotEqual(title_based, substantive)


class ShouldWidenContextTests(unittest.TestCase):
    def test_widens_when_method_context_is_sparse(self):
        self.assertTrue(
            _implementation_graph_should_widen_context({"sparse_method_context": True})
        )

    def test_does_not_widen_on_the_normal_path(self):
        self.assertFalse(
            _implementation_graph_should_widen_context({"sparse_method_context": False})
        )

    def test_does_not_widen_twice(self):
        state = {"sparse_method_context": True, "widened_context": True}
        self.assertFalse(_implementation_graph_should_widen_context(state))


class WidenContextNodeTests(unittest.TestCase):
    def test_rebuilds_context_and_explains_itself(self):
        state = {
            "paper": _FakePaper(),
            "breakdown": {},
            "warnings": ["earlier warning"],
            "sections": [
                _Section(0, "Intro", "a" * 100),
                _Section(1, "Unlabelled", "b" * 4000),
            ],
        }
        result = _implementation_graph_widen_context(state)

        self.assertTrue(result["widened_context"])
        self.assertIn(WIDENED_METHOD_CONTEXT_WARNING, result["warnings"])
        self.assertIn("earlier warning", result["warnings"])
        self.assertTrue(result["source_sections"])

    def test_leaves_context_alone_when_there_is_nothing_to_widen(self):
        result = _implementation_graph_widen_context(
            {"paper": _FakePaper(), "breakdown": {}, "sections": []}
        )
        self.assertTrue(result["widened_context"])
        self.assertNotIn("implementation_context", result)


class ImplementationGraphRoutingTests(unittest.TestCase):
    def _run(self, sparse: bool):
        calls = []

        def node(name, update=None):
            def run(state):
                calls.append(name)
                return update or {}

            return run

        graph = build_implementation_graph(
            ImplementationGraphNodes(
                load_paper=node("load_paper"),
                prepare_context=node(
                    "prepare_context", {"sparse_method_context": sparse}
                ),
                extract_algorithm=node("extract_algorithm"),
                analyze_gaps=node("analyze_gaps"),
                generate_pseudocode=node("generate_pseudocode"),
                generate_starter_code=node("generate_starter_code"),
                review_scaffold=node("review_scaffold"),
                build_response=node("build_response"),
                widen_context=node("widen_context", {"widened_context": True}),
                should_widen_context=_implementation_graph_should_widen_context,
            )
        )
        graph.invoke({"target_framework": "pytorch"})
        return calls

    def test_sparse_paper_routes_through_widen_context(self):
        calls = self._run(sparse=True)
        self.assertIn("widen_context", calls)
        self.assertEqual(
            calls[:4],
            ["load_paper", "prepare_context", "widen_context", "extract_algorithm"],
        )

    def test_normal_paper_skips_widen_context_entirely(self):
        calls = self._run(sparse=False)
        self.assertNotIn("widen_context", calls)
        self.assertEqual(
            calls[:3], ["load_paper", "prepare_context", "extract_algorithm"]
        )


if __name__ == "__main__":
    unittest.main()
