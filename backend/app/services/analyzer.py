import json

from openai import OpenAI

from app.config import settings

BREAKDOWN_FIELDS = [
    "problem",
    "method",
    "key_contributions",
    "results",
    "limitations",
    "future_work",
]

MAX_SECTION_CHARS = 80000


def analyze_paper(title: str, abstract: str, sections: list[dict]) -> dict:
    client = OpenAI(api_key=settings.openai_api_key)

    paper_text = f"Title: {title}\n\nAbstract: {abstract}\n\n"
    char_budget = MAX_SECTION_CHARS - len(paper_text)

    for s in sections:
        section_text = f"## {s['title']}\n{s['content']}\n\n"
        if len(section_text) > char_budget:
            paper_text += section_text[:char_budget]
            break
        paper_text += section_text
        char_budget -= len(section_text)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert research paper analyst. Given a paper's content, "
                    "produce a structured breakdown. Output ONLY a JSON object with these "
                    "exact keys:\n"
                    '- "problem": What problem does this paper address? (2-4 sentences)\n'
                    '- "method": What approach/method do the authors propose? (3-5 sentences)\n'
                    '- "key_contributions": What are the main contributions? (bulleted list as a string)\n'
                    '- "results": What are the key results/findings? (3-5 sentences)\n'
                    '- "limitations": What are the limitations or weaknesses? (2-4 sentences)\n'
                    '- "future_work": What future directions do the authors suggest or seem promising? (2-3 sentences)\n\n'
                    "Be specific and cite details from the paper. Do not hallucinate information "
                    "not present in the text. If a section cannot be determined from the paper, "
                    'say "Not explicitly discussed in the paper."'
                ),
            },
            {
                "role": "user",
                "content": paper_text,
            },
        ],
    )

    text = resp.choices[0].message.content.strip()
    breakdown = json.loads(text)

    for field in BREAKDOWN_FIELDS:
        if field not in breakdown:
            breakdown[field] = "Not explicitly discussed in the paper."

    return breakdown
