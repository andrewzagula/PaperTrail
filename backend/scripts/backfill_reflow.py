"""One-time repair of sections stored before text reflow existed.

Rows written by earlier ingests carry the PDF's visual line breaks. Reflow is
idempotent, so this is safe to run more than once; a second run reports zero
changes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import PaperSection
from app.services.text_reflow import reflow_text


def backfill_sections(db: Session) -> dict:
    changed_paper_ids: list[str] = []
    rows_changed = 0

    for section in db.query(PaperSection).all():
        reflowed = reflow_text(section.content or "")
        if reflowed == section.content:
            continue

        section.content = reflowed
        rows_changed += 1
        paper_id = str(section.paper_id)
        if paper_id not in changed_paper_ids:
            changed_paper_ids.append(paper_id)

    db.commit()
    return {"rows_changed": rows_changed, "paper_ids": changed_paper_ids}


def main() -> None:
    with SessionLocal() as db:
        result = backfill_sections(db)

    print("rows changed: " + str(result["rows_changed"]))
    if result["paper_ids"]:
        print("embeddings are now stale for these papers; re-embed them:")
        for paper_id in result["paper_ids"]:
            print("  POST http://localhost:8000/papers/" + paper_id + "/reembed")


if __name__ == "__main__":
    main()
