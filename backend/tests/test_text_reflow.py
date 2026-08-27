import unittest

from app.services.text_reflow import reflow_text

REPLACEMENT_CHAR = "�"
EM_DASH = "—"


class ReflowTextTests(unittest.TestCase):
    def test_mends_a_word_split_across_lines(self):
        self.assertEqual(
            reflow_text("achieved re-\nmarkable success"),
            "achieved remarkable success",
        )

    def test_keeps_the_hyphen_for_a_split_compound(self):
        """The continuation carries its own hyphen, so this is a real compound."""
        self.assertEqual(reflow_text("an end-\nto-end model"), "an end-to-end model")

    def test_joins_column_wrapped_lines_into_one_paragraph(self):
        self.assertEqual(
            reflow_text("first line\nsecond line"), "first line second line"
        )

    def test_keeps_paragraph_breaks(self):
        self.assertEqual(reflow_text("para one\n\npara two"), "para one\n\npara two")

    def test_collapses_runs_of_spaces(self):
        self.assertEqual(reflow_text("spaced    out"), "spaced out")

    def test_does_not_mend_before_an_uppercase_line(self):
        """A dash before a new sentence is not a split word."""
        self.assertEqual(reflow_text("a dash-\nThen more"), "a dash- Then more")

    def test_replaces_the_replacement_char_between_words_with_an_em_dash(self):
        self.assertEqual(
            reflow_text("Abstract" + REPLACEMENT_CHAR + "Large"),
            "Abstract" + EM_DASH + "Large",
        )

    def test_drops_a_stray_replacement_char(self):
        self.assertEqual(
            reflow_text("trailing " + REPLACEMENT_CHAR + " here"), "trailing here"
        )

    def test_is_idempotent(self):
        raw = "achieved re-\nmarkable success\n\nnext para\nwrapped"
        once = reflow_text(raw)
        self.assertEqual(reflow_text(once), once)

    def test_returns_empty_for_blank_input(self):
        self.assertEqual(reflow_text("   \n\n  "), "")

    def test_normalises_windows_line_endings(self):
        self.assertEqual(reflow_text("one\r\ntwo"), "one two")


class SplitIntoSectionsReflowTests(unittest.TestCase):
    def test_section_content_comes_back_reflowed(self):
        from app.services.section_splitter import split_into_sections

        raw = (
            "Introduction\nachieved re-\nmarkable success\n\n"
            "Method\nwe pro-\npose a model"
        )
        contents = " ".join(
            section["content"] for section in split_into_sections(raw)
        )

        self.assertIn("remarkable success", contents)
        self.assertNotIn("re-\nmarkable", contents)

    def test_headings_are_still_detected(self):
        """Reflow must run after heading detection, never before."""
        from app.services.section_splitter import split_into_sections

        raw = "Introduction\nsome body text\n\nMethod\nmore body text"
        titles = [section["title"] for section in split_into_sections(raw)]

        self.assertIn("Introduction", titles)
        self.assertIn("Method", titles)


if __name__ == "__main__":
    unittest.main()
