"""One-time repair of arxiv_url values stored before ingest canonicalized them.

Rows written by earlier ingests hold whatever the user pasted - a bare id or a
schemeless link. Rewriting to the canonical abs URL is idempotent, so this is
safe to run more than once; a second run reports zero changes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import Paper
from app.services.arxiv_fetcher import ARXIV_ABS_URL, extract_arxiv_id


def backfill_arxiv_urls(db: Session) -> dict:
    rows_changed = 0

    for paper in db.query(Paper).filter(Paper.arxiv_url.isnot(None)).all():
        arxiv_id = extract_arxiv_id(paper.arxiv_url)
        if not arxiv_id:
            continue

        canonical = ARXIV_ABS_URL.format(paper_id=arxiv_id)
        if canonical == paper.arxiv_url:
            continue

        paper.arxiv_url = canonical
        rows_changed += 1

    db.commit()
    return {"rows_changed": rows_changed}


def main() -> None:
    with SessionLocal() as db:
        result = backfill_arxiv_urls(db)

    print("rows changed: " + str(result["rows_changed"]))


if __name__ == "__main__":
    main()
