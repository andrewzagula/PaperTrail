"""Turning PDF-extracted text back into prose.

PyMuPDF returns text carrying the page's visual line breaks. Papers are
typeset in narrow columns, so those breaks land mid-sentence and words are
hyphenated across them. Everything downstream - embeddings, chat context,
every structured workflow step - reads this text, so it is mended once at
ingest rather than at each point of use.
"""

from __future__ import annotations

import re

REPLACEMENT_CHAR = "�"
EM_DASH = "—"

# A line-ending hyphen followed by a lowercase continuation. The continuation
# is captured so a compound can be told apart from a word split for width.
_HYPHEN_LINE_BREAK = re.compile(r"([A-Za-z])-\n([a-z][A-Za-z-]*)")

# U+FFFD standing in for a dash the extractor lost, as in "Abstract?Large".
_REPLACEMENT_BETWEEN_WORDS = re.compile(r"(?<=\w)" + REPLACEMENT_CHAR + r"(?=\w)")

_BLANK_LINE = re.compile(r"\n\s*\n")
_SPACE_RUN = re.compile(r"[ \t]+")


def _mend_hyphen(match: re.Match) -> str:
    head, tail = match.group(1), match.group(2)
    # A continuation carrying its own hyphen is a compound the typesetter
    # broke ("end-" / "to-end"), not one word split for width.
    if "-" in tail:
        return head + "-" + tail
    return head + tail


def reflow_text(raw: str) -> str:
    """Rejoin column-wrapped lines into paragraphs. Idempotent."""
    if not raw or not raw.strip():
        return ""

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _REPLACEMENT_BETWEEN_WORDS.sub(EM_DASH, text)
    text = text.replace(REPLACEMENT_CHAR, "")

    paragraphs = []
    for block in _BLANK_LINE.split(text):
        block = _HYPHEN_LINE_BREAK.sub(_mend_hyphen, block)
        block = block.replace("\n", " ")
        block = _SPACE_RUN.sub(" ", block).strip()
        if block:
            paragraphs.append(block)

    return "\n\n".join(paragraphs)
