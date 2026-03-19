"""Paper ingestion and retrieval endpoints."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.models import Paper, PaperSection, User
from app.services.arxiv_fetcher import (
    download_arxiv_pdf,
    extract_arxiv_id,
    fetch_arxiv_metadata,
)
from app.services.embedder import embed_and_store_sections
from app.services.pdf_parser import extract_metadata, extract_text
from app.services.section_splitter import split_into_sections

router = APIRouter(prefix="/papers", tags=["papers"])

PDF_DIR = settings.data_dir / "pdfs"
PDF_DIR.mkdir(exist_ok=True)

DEFAULT_USER_EMAIL = "local@papertrail.dev"


# --- Request / Response schemas ---


class IngestArxivRequest(BaseModel):
    arxiv_url: str


class SectionResponse(BaseModel):
    id: str
    section_title: str
    section_order: int
    content: str
    chunk_index: int | None

    class Config:
        from_attributes = True


class PaperResponse(BaseModel):
    id: str
    title: str
    authors: str | None
    abstract: str | None
    arxiv_url: str | None
    created_at: str
    sections: list[SectionResponse]

    class Config:
        from_attributes = True


class PaperListItem(BaseModel):
    id: str
    title: str
    authors: str | None
    abstract: str | None
    arxiv_url: str | None
    created_at: str

    class Config:
        from_attributes = True


# --- Helpers ---


def _get_or_create_default_user(db: Session) -> User:
    """Get or create the default local user."""
    user = db.query(User).filter(User.email == DEFAULT_USER_EMAIL).first()
    if not user:
        user = User(email=DEFAULT_USER_EMAIL, name="Local User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _store_paper(
    db: Session,
    user_id: uuid.UUID,
    title: str,
    authors: str,
    abstract: str,
    arxiv_url: str | None,
    pdf_path: str,
    raw_text: str,
    sections_data: list[dict],
) -> Paper:
    """Create Paper and PaperSection rows, then embed."""
    paper = Paper(
        user_id=user_id,
        title=title,
        authors=authors,
        abstract=abstract,
        arxiv_url=arxiv_url,
        pdf_path=pdf_path,
        raw_text=raw_text,
    )
    db.add(paper)
    db.flush()  # get paper.id

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

    db.commit()
    db.refresh(paper)

    # Embed sections into ChromaDB (non-blocking — paper is saved even if embedding fails)
    num_chunks = 0
    try:
        num_chunks = embed_and_store_sections(
            paper_id=str(paper.id),
            sections=section_records,
        )
    except Exception as e:
        print(f"Warning: embedding failed for paper {paper.id}: {e}")

    return paper, num_chunks


# --- Endpoints ---


@router.post("/ingest/arxiv")
async def ingest_arxiv(req: IngestArxivRequest, db: Session = Depends(get_db)):
    """Ingest a paper from an arXiv URL."""
    arxiv_id = extract_arxiv_id(req.arxiv_url)
    if not arxiv_id:
        raise HTTPException(status_code=400, detail="Invalid arXiv URL or ID")

    user = _get_or_create_default_user(db)

    # Fetch metadata and PDF
    metadata = await fetch_arxiv_metadata(arxiv_id)
    pdf_path = await download_arxiv_pdf(arxiv_id)

    # Parse PDF
    raw_text = extract_text(pdf_path)
    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from PDF")

    # Split into sections
    sections_data = split_into_sections(raw_text)

    # Use arXiv metadata (more reliable than PDF metadata)
    title = metadata["title"] or "Untitled"
    authors = metadata["authors"] or ""
    abstract = metadata["abstract"] or ""

    paper, num_chunks = _store_paper(
        db=db,
        user_id=user.id,
        title=title,
        authors=authors,
        abstract=abstract,
        arxiv_url=req.arxiv_url,
        pdf_path=str(pdf_path),
        raw_text=raw_text,
        sections_data=sections_data,
    )

    return {
        "id": str(paper.id),
        "title": paper.title,
        "num_sections": len(sections_data),
        "num_chunks_embedded": num_chunks,
    }


@router.post("/ingest/pdf")
async def ingest_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Ingest a paper from a direct PDF upload."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    user = _get_or_create_default_user(db)

    # Save uploaded file
    pdf_path = PDF_DIR / f"{uuid.uuid4()}.pdf"
    content = await file.read()
    pdf_path.write_bytes(content)

    # Parse PDF
    raw_text = extract_text(pdf_path)
    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from PDF")

    # Extract metadata from PDF
    pdf_meta = extract_metadata(pdf_path)
    sections_data = split_into_sections(raw_text)

    # Try to get title from PDF metadata, fall back to filename
    title = pdf_meta["title"] or Path(file.filename).stem
    authors = pdf_meta["authors"] or ""

    # Try to extract abstract from sections
    abstract = ""
    for s in sections_data:
        if s["title"].lower() in ("abstract", "preamble"):
            abstract = s["content"][:2000]
            break

    paper, num_chunks = _store_paper(
        db=db,
        user_id=user.id,
        title=title,
        authors=authors,
        abstract=abstract,
        arxiv_url=None,
        pdf_path=str(pdf_path),
        raw_text=raw_text,
        sections_data=sections_data,
    )

    return {
        "id": str(paper.id),
        "title": paper.title,
        "num_sections": len(sections_data),
        "num_chunks_embedded": num_chunks,
    }


@router.get("/", response_model=list[PaperListItem])
def list_papers(db: Session = Depends(get_db)):
    """List all ingested papers."""
    user = _get_or_create_default_user(db)
    papers = (
        db.query(Paper)
        .filter(Paper.user_id == user.id)
        .order_by(Paper.created_at.desc())
        .all()
    )
    return [
        PaperListItem(
            id=str(p.id),
            title=p.title,
            authors=p.authors,
            abstract=p.abstract,
            arxiv_url=p.arxiv_url,
            created_at=p.created_at.isoformat() if p.created_at else "",
        )
        for p in papers
    ]


@router.get("/{paper_id}", response_model=PaperResponse)
def get_paper(paper_id: str, db: Session = Depends(get_db)):
    """Get a paper with all its sections."""
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")
    paper = db.query(Paper).filter(Paper.id == pid).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    sections = (
        db.query(PaperSection)
        .filter(PaperSection.paper_id == paper.id)
        .order_by(PaperSection.section_order)
        .all()
    )

    return PaperResponse(
        id=str(paper.id),
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        arxiv_url=paper.arxiv_url,
        created_at=paper.created_at.isoformat() if paper.created_at else "",
        sections=[
            SectionResponse(
                id=str(s.id),
                section_title=s.section_title,
                section_order=s.section_order,
                content=s.content,
                chunk_index=s.chunk_index,
            )
            for s in sections
        ],
    )


@router.delete("/{paper_id}")
def delete_paper(paper_id: str, db: Session = Depends(get_db)):
    """Delete a paper and its sections + embeddings."""
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")
    paper = db.query(Paper).filter(Paper.id == pid).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Delete embeddings from ChromaDB
    from app.services.vector_store import delete_by_paper
    delete_by_paper(paper_id)

    # Delete from SQLite (cascade deletes sections)
    db.delete(paper)
    db.commit()

    return {"status": "deleted", "id": paper_id}
