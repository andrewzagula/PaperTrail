"""Discovery endpoints: question → search → rank → ingest."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import DiscoveryResult, DiscoveryRun, User

router = APIRouter(prefix="/discover", tags=["discovery"])

DEFAULT_USER_EMAIL = "local@papertrail.dev"


# --- Request / Response schemas ---


class DiscoverRequest(BaseModel):
    question: str
    max_results: int = 10


class DiscoveryResultResponse(BaseModel):
    id: str
    arxiv_id: str
    title: str
    authors: str | None
    abstract: str | None
    published: str | None
    relevance_score: float | None
    relevance_reason: str | None
    rank_order: int
    paper_id: str | None  # set if ingested

    class Config:
        from_attributes = True


class DiscoveryRunResponse(BaseModel):
    id: str
    question: str
    status: str
    generated_queries: list[str] | None
    budget_used: dict | None
    error_message: str | None
    created_at: str
    results: list[DiscoveryResultResponse]

    class Config:
        from_attributes = True


class DiscoveryRunListItem(BaseModel):
    id: str
    question: str
    status: str
    created_at: str
    num_results: int

    class Config:
        from_attributes = True


# --- Helpers ---


def _get_or_create_default_user(db: Session) -> User:
    user = db.query(User).filter(User.email == DEFAULT_USER_EMAIL).first()
    if not user:
        user = User(email=DEFAULT_USER_EMAIL, name="Local User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _run_to_response(run: DiscoveryRun) -> DiscoveryRunResponse:
    return DiscoveryRunResponse(
        id=str(run.id),
        question=run.question,
        status=run.status,
        generated_queries=run.generated_queries,
        budget_used=run.budget_used,
        error_message=run.error_message,
        created_at=run.created_at.isoformat() if run.created_at else "",
        results=[
            DiscoveryResultResponse(
                id=str(r.id),
                arxiv_id=r.arxiv_id,
                title=r.title,
                authors=r.authors,
                abstract=r.abstract,
                published=r.published,
                relevance_score=r.relevance_score,
                relevance_reason=r.relevance_reason,
                rank_order=r.rank_order,
                paper_id=str(r.paper_id) if r.paper_id else None,
            )
            for r in sorted(run.results, key=lambda x: x.rank_order)
        ],
    )


async def _execute_discovery(run_id: uuid.UUID, question: str, max_results: int):
    """Run discovery pipeline in the background and persist results."""
    from app.database import SessionLocal
    from app.services.discovery import run_discovery

    db = SessionLocal()
    try:
        run = db.query(DiscoveryRun).filter(DiscoveryRun.id == run_id).first()
        if not run:
            return

        run.status = "running"
        db.commit()

        try:
            result = await run_discovery(
                question=question,
                max_return=max_results,
            )

            run.generated_queries = result["queries"]
            run.budget_used = result["budget_used"]

            for i, paper in enumerate(result["ranked_results"]):
                dr = DiscoveryResult(
                    run_id=run.id,
                    arxiv_id=paper["arxiv_id"],
                    title=paper["title"],
                    authors=paper["authors"],
                    abstract=paper["abstract"],
                    published=paper["published"],
                    relevance_score=paper["relevance_score"],
                    relevance_reason=paper["relevance_reason"],
                    rank_order=i + 1,
                )
                db.add(dr)

            run.status = "complete"
            db.commit()
        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            db.commit()
    finally:
        db.close()


# --- Endpoints ---


@router.post("/", response_model=DiscoveryRunResponse)
async def start_discovery(
    req: DiscoverRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a discovery run from a research question."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    user = _get_or_create_default_user(db)

    run = DiscoveryRun(
        user_id=user.id,
        question=req.question.strip(),
        status="pending",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(
        _execute_discovery, run.id, req.question.strip(), req.max_results
    )

    return _run_to_response(run)


@router.get("/", response_model=list[DiscoveryRunListItem])
def list_discovery_runs(db: Session = Depends(get_db)):
    """List all past discovery runs."""
    user = _get_or_create_default_user(db)
    runs = (
        db.query(DiscoveryRun)
        .filter(DiscoveryRun.user_id == user.id)
        .order_by(DiscoveryRun.created_at.desc())
        .all()
    )
    return [
        DiscoveryRunListItem(
            id=str(r.id),
            question=r.question,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else "",
            num_results=len(r.results),
        )
        for r in runs
    ]


@router.get("/{run_id}", response_model=DiscoveryRunResponse)
def get_discovery_run(run_id: str, db: Session = Depends(get_db)):
    """Get a discovery run with its ranked results."""
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID")

    run = db.query(DiscoveryRun).filter(DiscoveryRun.id == rid).first()
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    return _run_to_response(run)


@router.post("/{run_id}/ingest/{result_id}")
async def ingest_discovery_result(
    run_id: str,
    result_id: str,
    db: Session = Depends(get_db),
):
    """Ingest a discovery result into the paper library using the existing pipeline."""
    try:
        rid = uuid.UUID(run_id)
        rsid = uuid.UUID(result_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    run = db.query(DiscoveryRun).filter(DiscoveryRun.id == rid).first()
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    result = (
        db.query(DiscoveryResult)
        .filter(DiscoveryResult.id == rsid, DiscoveryResult.run_id == rid)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Discovery result not found")

    if result.paper_id:
        return {
            "status": "already_ingested",
            "paper_id": str(result.paper_id),
        }

    # Use existing ingestion pipeline
    from app.services.arxiv_fetcher import download_arxiv_pdf, fetch_arxiv_metadata
    from app.services.embedder import embed_and_store_sections
    from app.services.pdf_parser import extract_text
    from app.services.section_splitter import split_into_sections
    from app.models.models import Paper, PaperSection

    user = _get_or_create_default_user(db)

    # Fetch metadata + PDF
    metadata = await fetch_arxiv_metadata(result.arxiv_id)
    pdf_path = await download_arxiv_pdf(result.arxiv_id)

    raw_text = extract_text(pdf_path)
    if not raw_text.strip():
        raise HTTPException(
            status_code=422, detail="Could not extract text from PDF"
        )

    sections_data = split_into_sections(raw_text)

    paper = Paper(
        user_id=user.id,
        title=metadata["title"] or result.title,
        authors=metadata["authors"] or result.authors or "",
        abstract=metadata["abstract"] or result.abstract or "",
        arxiv_url=f"https://arxiv.org/abs/{result.arxiv_id}",
        pdf_path=str(pdf_path),
        raw_text=raw_text,
    )
    db.add(paper)
    db.flush()

    section_records = []
    for s in sections_data:
        section = PaperSection(
            paper_id=paper.id,
            section_title=s["title"],
            section_order=s["order"],
            content=s["content"],
        )
        db.add(section)
        db.flush()
        section_records.append({
            "id": str(section.id),
            "title": s["title"],
            "content": s["content"],
        })

    # Link discovery result to paper
    result.paper_id = paper.id
    db.commit()
    db.refresh(paper)

    # Embed (non-fatal)
    num_chunks = 0
    try:
        num_chunks = embed_and_store_sections(
            paper_id=str(paper.id),
            sections=section_records,
        )
    except Exception as e:
        print(f"Warning: embedding failed for paper {paper.id}: {e}")

    return {
        "status": "ingested",
        "paper_id": str(paper.id),
        "title": paper.title,
        "num_sections": len(sections_data),
        "num_chunks_embedded": num_chunks,
    }
