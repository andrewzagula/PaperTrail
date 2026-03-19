"""Split raw paper text into sections using heading heuristics."""

import re

# Common section headings in research papers
STANDARD_HEADINGS = [
    "abstract",
    "introduction",
    "related work",
    "background",
    "preliminaries",
    "method",
    "methodology",
    "methods",
    "approach",
    "proposed method",
    "model",
    "architecture",
    "experiments",
    "experimental setup",
    "experimental results",
    "results",
    "evaluation",
    "discussion",
    "analysis",
    "ablation",
    "ablation study",
    "conclusion",
    "conclusions",
    "future work",
    "limitations",
    "references",
    "appendix",
    "acknowledgements",
    "acknowledgments",
]

# Patterns for detecting section headings
HEADING_PATTERNS = [
    # "1. Introduction" or "1 Introduction"
    re.compile(
        r"^(\d+\.?\s+)([A-Z][A-Za-z\s&:–-]{2,60})$", re.MULTILINE
    ),
    # "A. Appendix" or "A Appendix"
    re.compile(
        r"^([A-Z]\.?\s+)([A-Z][A-Za-z\s&:–-]{2,60})$", re.MULTILINE
    ),
    # "INTRODUCTION" (all caps, standalone line)
    re.compile(
        r"^([A-Z][A-Z\s&:–-]{2,60})$", re.MULTILINE
    ),
    # "Introduction" or "Related Work" (title-case, standalone line)
    re.compile(
        r"^([A-Z][a-z]+(?:\s+[A-Za-z]+){0,5})$", re.MULTILINE
    ),
]


def split_into_sections(raw_text: str) -> list[dict]:
    """Split paper text into sections.

    Returns a list of dicts: [{"title": str, "content": str, "order": int}, ...]
    """
    lines = raw_text.split("\n")
    sections: list[dict] = []
    current_title = "Preamble"
    current_lines: list[str] = []
    order = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_lines.append("")
            continue

        heading = _detect_heading(stripped)
        if heading:
            # Save previous section
            content = "\n".join(current_lines).strip()
            if content:
                sections.append({
                    "title": current_title,
                    "content": content,
                    "order": order,
                })
                order += 1
            current_title = heading
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    content = "\n".join(current_lines).strip()
    if content:
        sections.append({
            "title": current_title,
            "content": content,
            "order": order,
        })

    # If no sections were detected (just Preamble), try to at least
    # separate the abstract from the body
    if len(sections) <= 1:
        sections = _fallback_split(raw_text)

    return sections


def _detect_heading(line: str) -> str | None:
    """Check if a line is a section heading. Returns the cleaned heading or None."""
    # Pattern 1: Numbered headings like "1. Introduction" or "3 Method"
    # These are high-confidence — accept if they match a known heading
    numbered_match = HEADING_PATTERNS[0].match(line)
    if numbered_match:
        heading = numbered_match.group(2).strip()
        if _is_known_heading(heading):
            return heading

    # Pattern 2: Letter-prefixed like "A. Appendix"
    letter_match = HEADING_PATTERNS[1].match(line)
    if letter_match:
        heading = letter_match.group(2).strip()
        if _is_known_heading(heading):
            return heading

    # Pattern 3: ALL CAPS standalone line — only accept if it matches a known heading
    caps_match = HEADING_PATTERNS[2].match(line)
    if caps_match:
        heading = caps_match.group(1).strip()
        if _is_known_heading(heading):
            return heading

    # Pattern 4: Title-case standalone line — only accept if it matches a known heading
    title_match = HEADING_PATTERNS[3].match(line)
    if title_match:
        heading = title_match.group(1).strip()
        if _is_known_heading(heading):
            return heading

    return None


def _is_known_heading(text: str) -> bool:
    """Check if text matches a known section heading."""
    normalized = text.lower().strip().rstrip(":")
    # Must be at least 5 characters to avoid matching table labels like SRC, REF
    if len(normalized) < 5:
        return False
    # Direct match against known headings
    if normalized in STANDARD_HEADINGS:
        return True
    # Check if the normalized text contains a known heading as a whole word
    for heading in STANDARD_HEADINGS:
        if heading in normalized:
            return True
    return False


def _fallback_split(raw_text: str) -> list[dict]:
    """If heading detection fails, split into rough chunks."""
    # Try to find "Abstract" in the text
    abstract_match = re.search(
        r"(?i)\babstract\b[:\s]*(.*?)(?=\n\n|\bintroduction\b|\b1[\.\s])",
        raw_text,
        re.DOTALL,
    )

    sections = []
    if abstract_match:
        sections.append({
            "title": "Abstract",
            "content": abstract_match.group(1).strip(),
            "order": 0,
        })
        rest = raw_text[abstract_match.end():].strip()
        if rest:
            sections.append({
                "title": "Body",
                "content": rest,
                "order": 1,
            })
    else:
        sections.append({
            "title": "Full Text",
            "content": raw_text.strip(),
            "order": 0,
        })

    return sections
