import re

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

HEADING_PATTERNS = [
    re.compile(
        r"^(\d+\.?\s+)([A-Z][A-Za-z\s&:–-]{2,60})$", re.MULTILINE
    ),
    re.compile(
        r"^([A-Z]\.?\s+)([A-Z][A-Za-z\s&:–-]{2,60})$", re.MULTILINE
    ),
    re.compile(
        r"^([A-Z][A-Z\s&:–-]{2,60})$", re.MULTILINE
    ),
    re.compile(
        r"^([A-Z][a-z]+(?:\s+[A-Za-z]+){0,5})$", re.MULTILINE
    ),
]


def split_into_sections(raw_text: str) -> list[dict]:
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

    content = "\n".join(current_lines).strip()
    if content:
        sections.append({
            "title": current_title,
            "content": content,
            "order": order,
        })

    if len(sections) <= 1:
        sections = _fallback_split(raw_text)

    return sections


def _detect_heading(line: str) -> str | None:
    numbered_match = HEADING_PATTERNS[0].match(line)
    if numbered_match:
        heading = numbered_match.group(2).strip()
        if _is_known_heading(heading):
            return heading

    letter_match = HEADING_PATTERNS[1].match(line)
    if letter_match:
        heading = letter_match.group(2).strip()
        if _is_known_heading(heading):
            return heading

    caps_match = HEADING_PATTERNS[2].match(line)
    if caps_match:
        heading = caps_match.group(1).strip()
        if _is_known_heading(heading):
            return heading

    title_match = HEADING_PATTERNS[3].match(line)
    if title_match:
        heading = title_match.group(1).strip()
        if _is_known_heading(heading):
            return heading

    return None


def _is_known_heading(text: str) -> bool:
    normalized = text.lower().strip().rstrip(":")
    if len(normalized) < 5:
        return False
    if normalized in STANDARD_HEADINGS:
        return True
    for heading in STANDARD_HEADINGS:
        if heading in normalized:
            return True
    return False


def _fallback_split(raw_text: str) -> list[dict]:
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
