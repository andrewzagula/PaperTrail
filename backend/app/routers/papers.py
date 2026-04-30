import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.llm import get_provider_error_response
from app.models.models import Chat, Paper, PaperSection, User
from app.services.arxiv_fetcher import (
    download_arxiv_pdf,
    extract_arxiv_id,
    fetch_arxiv_metadata,
)
from app.services.errors import UserSafeServiceError
from app.services.paper_embeddings import (
    EMBEDDING_STATUS_READY,
    get_paper_embedding_status,
    get_paper_embedding_status_map,
    sync_paper_embeddings,
)
from app.services.pdf_parser import extract_metadata, extract_text
from app.services.section_splitter import split_into_sections
from app.services.vector_store import delete_by_paper

router = APIRouter(prefix="/papers", tags=["papers"])

PDF_DIR = settings.data_dir / "pdfs"
PDF_DIR.mkdir(exist_ok=True)

DEFAULT_USER_EMAIL = "local@papertrail.dev"
PDF_TEXT_EXTRACTION_DETAIL = "Could not extract text from PDF."


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


class PaperEmbeddingMetadata(BaseModel):
    embedding_status: str
    embedding_provider: str
    embedding_model: str
    embedded_at: str | None

    class Config:
        from_attributes = True


class PaperResponse(PaperEmbeddingMetadata):
    id: str
    title: str
    authors: str | None
    abstract: str | None
    arxiv_url: str | None
    created_at: str
    structured_breakdown: dict | None
    sections: list[SectionResponse]

    class Config:
        from_attributes = True


class PaperListItem(PaperEmbeddingMetadata):
    id: str
    title: str
    authors: str | None
    abstract: str | None
    arxiv_url: str | None
    created_at: str
    has_structured_breakdown: bool

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: list | None
    created_at: str

    class Config:
        from_attributes = True


class ReembedRequest(BaseModel):
    paper_ids: list[str] | None = None
    force: bool = False


class ReembedPaperResponse(PaperEmbeddingMetadata):
    paper_id: str
    title: str
    num_chunks_embedded: int

    class Config:
        from_attributes = True

def _get_or_create_default_user(db: Session) -> User:
    user = db.query(User).filter(User.email == DEFAULT_USER_EMAIL).first()
    if not user:
        user = User(email=DEFAULT_USER_EMAIL, name="Local User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _serialize_sections_for_embedding(sections: list[PaperSection]) -> list[dict]:
    return [
        {
            "id": str(section.id),
            "title": section.section_title,
            "content": section.content,
        }
        for section in sections
    ]


def _get_paper_or_404(db: Session, paper_id: str) -> Paper:
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    paper = db.query(Paper).filter(Paper.id == pid).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


def _raise_user_safe_http_error(error: UserSafeServiceError):
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


def _build_reembed_response(
    db: Session,
    paper: Paper,
    num_chunks_embedded: int,
) -> ReembedPaperResponse:
    embedding_status = get_paper_embedding_status(db, paper.id)
    return ReembedPaperResponse(
        paper_id=str(paper.id),
        title=paper.title,
        num_chunks_embedded=num_chunks_embedded,
        **embedding_status.to_response_fields(),
    )


def _reembed_paper(db: Session, paper: Paper) -> ReembedPaperResponse:
    sections = (
        db.query(PaperSection)
        .filter(PaperSection.paper_id == paper.id)
        .order_by(PaperSection.section_order)
        .all()
    )
    num_chunks_embedded = sync_paper_embeddings(
        db,
        paper.id,
        _serialize_sections_for_embedding(sections),
        replace_active_embeddings=True,
    )
    return _build_reembed_response(db, paper, num_chunks_embedded)


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

    db.commit()
    db.refresh(paper)

    num_chunks = 0
    try:
        num_chunks = sync_paper_embeddings(
            db,
            paper.id,
            section_records,
        )
    except Exception as e:
        print(f"Warning: embedding failed for paper {paper.id}: {e}")

    return paper, num_chunks


@router.post("/ingest/arxiv")
async def ingest_arxiv(req: IngestArxivRequest, db: Session = Depends(get_db)):
    arxiv_id = extract_arxiv_id(req.arxiv_url)
    if not arxiv_id:
        raise HTTPException(status_code=400, detail="Invalid arXiv URL or ID")

    user = _get_or_create_default_user(db)

    try:
        metadata = await fetch_arxiv_metadata(arxiv_id)
        pdf_path = await download_arxiv_pdf(arxiv_id)
        raw_text = extract_text(pdf_path)
    except UserSafeServiceError as error:
        _raise_user_safe_http_error(error)

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail=PDF_TEXT_EXTRACTION_DETAIL)

    sections_data = split_into_sections(raw_text)

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
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    user = _get_or_create_default_user(db)

    pdf_path = PDF_DIR / f"{uuid.uuid4()}.pdf"
    content = await file.read()
    pdf_path.write_bytes(content)

    try:
        raw_text = extract_text(pdf_path)
    except UserSafeServiceError as error:
        pdf_path.unlink(missing_ok=True)
        _raise_user_safe_http_error(error)

    if not raw_text.strip():
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=PDF_TEXT_EXTRACTION_DETAIL)

    try:
        pdf_meta = extract_metadata(pdf_path)
    except UserSafeServiceError as error:
        pdf_path.unlink(missing_ok=True)
        _raise_user_safe_http_error(error)
    sections_data = split_into_sections(raw_text)

    title = pdf_meta["title"] or Path(file.filename).stem
    authors = pdf_meta["authors"] or ""

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


@router.post("/reembed")
def bulk_reembed_papers(req: ReembedRequest, db: Session = Depends(get_db)):
    user = _get_or_create_default_user(db)
    paper_query = (
        db.query(Paper)
        .filter(Paper.user_id == user.id)
        .order_by(Paper.created_at.desc())
    )

    if req.paper_ids is not None:
        try:
            requested_ids = [uuid.UUID(paper_id) for paper_id in req.paper_ids]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid paper ID")

        papers = paper_query.filter(Paper.id.in_(requested_ids)).all()
        found_ids = {paper.id for paper in papers}
        missing_ids = [
            str(requested_id)
            for requested_id in requested_ids
            if requested_id not in found_ids
        ]
        if missing_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Paper not found: {missing_ids[0]}",
            )
    else:
        papers = paper_query.all()

    status_map = get_paper_embedding_status_map(db, [paper.id for paper in papers])
    target_papers: list[Paper] = []
    skipped_count = 0
    for paper in papers:
        paper_status = status_map[str(paper.id)]
        if not req.force and paper_status.status == EMBEDDING_STATUS_READY:
            skipped_count += 1
            continue
        target_papers.append(paper)

    results: list[ReembedPaperResponse] = []
    for paper in target_papers:
        try:
            results.append(_reembed_paper(db, paper))
        except Exception as error:
            mapped_error = get_provider_error_response(error)
            if mapped_error:
                status_code, detail = mapped_error
                raise HTTPException(status_code=status_code, detail=detail) from error
            raise

    return {
        "requested_count": len(papers),
        "reembedded_count": len(results),
        "skipped_count": skipped_count,
        "results": [result.model_dump() for result in results],
    }


@router.get("/", response_model=list[PaperListItem])
def list_papers(db: Session = Depends(get_db)):
    user = _get_or_create_default_user(db)
    papers = (
        db.query(Paper)
        .filter(Paper.user_id == user.id)
        .order_by(Paper.created_at.desc())
        .all()
    )
    status_map = get_paper_embedding_status_map(db, [paper.id for paper in papers])
    return [
        PaperListItem(
            id=str(p.id),
            title=p.title,
            authors=p.authors,
            abstract=p.abstract,
            arxiv_url=p.arxiv_url,
            created_at=p.created_at.isoformat() if p.created_at else "",
            has_structured_breakdown=bool(p.structured_breakdown),
            **status_map[str(p.id)].to_response_fields(),
        )
        for p in papers
    ]


@router.get("/{paper_id}", response_model=PaperResponse)
def get_paper(paper_id: str, db: Session = Depends(get_db)):
    paper = _get_paper_or_404(db, paper_id)

    sections = (
        db.query(PaperSection)
        .filter(PaperSection.paper_id == paper.id)
        .order_by(PaperSection.section_order)
        .all()
    )
    embedding_status = get_paper_embedding_status(db, paper.id)

    return PaperResponse(
        id=str(paper.id),
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        arxiv_url=paper.arxiv_url,
        created_at=paper.created_at.isoformat() if paper.created_at else "",
        structured_breakdown=paper.structured_breakdown,
        **embedding_status.to_response_fields(),
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


@router.post("/{paper_id}/reembed", response_model=ReembedPaperResponse)
def reembed_paper_endpoint(paper_id: str, db: Session = Depends(get_db)):
    paper = _get_paper_or_404(db, paper_id)

    try:
        return _reembed_paper(db, paper)
    except Exception as error:
        mapped_error = get_provider_error_response(error)
        if mapped_error:
            status_code, detail = mapped_error
            raise HTTPException(status_code=status_code, detail=detail) from error
        raise


@router.delete("/{paper_id}")
def delete_paper(paper_id: str, db: Session = Depends(get_db)):
    paper = _get_paper_or_404(db, paper_id)
    delete_by_paper(paper_id)

    db.delete(paper)
    db.commit()

    return {"status": "deleted", "id": paper_id}


@router.post("/{paper_id}/analyze")
def analyze_paper_endpoint(paper_id: str, db: Session = Depends(get_db)):
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    paper = db.query(Paper).filter(Paper.id == pid).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.structured_breakdown:
        return paper.structured_breakdown

    sections = (
        db.query(PaperSection)
        .filter(PaperSection.paper_id == paper.id)
        .order_by(PaperSection.section_order)
        .all()
    )

    sections_data = [
        {"title": s.section_title, "content": s.content}
        for s in sections
    ]

    from app.services.analyzer import analyze_paper
    try:
        breakdown = analyze_paper(
            title=paper.title,
            abstract=paper.abstract or "",
            sections=sections_data,
        )
    except Exception as error:
        mapped_error = get_provider_error_response(error)
        if mapped_error:
            status_code, detail = mapped_error
            raise HTTPException(status_code=status_code, detail=detail) from error
        raise

    paper.structured_breakdown = breakdown
    db.commit()

    return breakdown


@router.get("/{paper_id}/chats", response_model=list[ChatMessageResponse])
def get_chat_history(paper_id: str, db: Session = Depends(get_db)):
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    paper = db.query(Paper).filter(Paper.id == pid).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    chats = (
        db.query(Chat)
        .filter(Chat.paper_id == pid)
        .order_by(Chat.created_at)
        .all()
    )

    return [
        ChatMessageResponse(
            id=str(c.id),
            role=c.role,
            content=c.content,
            citations=c.citations,
            created_at=c.created_at.isoformat() if c.created_at else "",
        )
        for c in chats
    ]


@router.post("/{paper_id}/chat", response_model=ChatMessageResponse)
def chat_with_paper(paper_id: str, req: ChatRequest, db: Session = Depends(get_db)):
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    paper = db.query(Paper).filter(Paper.id == pid).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    user = _get_or_create_default_user(db)

    user_msg = Chat(
        user_id=user.id,
        paper_id=pid,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    db.flush()

    history = (
        db.query(Chat)
        .filter(Chat.paper_id == pid)
        .order_by(Chat.created_at)
        .all()
    )
    history_dicts = [
        {"role": c.role, "content": c.content}
        for c in history
        if c.id != user_msg.id
    ]

    from app.services.chat_rag import generate_chat_response
    embedding_status = get_paper_embedding_status(db, paper.id)

    try:
        result = generate_chat_response(
            paper_id=paper_id,
            paper_title=paper.title,
            query=req.message,
            history=history_dicts,
            embedding_status=embedding_status.status,
        )
    except Exception as error:
        mapped_error = get_provider_error_response(error)
        if mapped_error:
            status_code, detail = mapped_error
            raise HTTPException(status_code=status_code, detail=detail) from error
        raise

    assistant_msg = Chat(
        user_id=user.id,
        paper_id=pid,
        role="assistant",
        content=result["answer"],
        citations=result["citations"],
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return ChatMessageResponse(
        id=str(assistant_msg.id),
        role="assistant",
        content=result["answer"],
        citations=result["citations"],
        created_at=assistant_msg.created_at.isoformat() if assistant_msg.created_at else "",
    )


@router.delete("/{paper_id}/chats")
def clear_chat_history(paper_id: str, db: Session = Depends(get_db)):
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    paper = db.query(Paper).filter(Paper.id == pid).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    db.query(Chat).filter(Chat.paper_id == pid).delete()
    db.commit()

    return {"status": "cleared", "paper_id": paper_id}
