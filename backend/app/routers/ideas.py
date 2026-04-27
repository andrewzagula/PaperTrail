import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm import get_provider_error_response
from app.models.models import SavedItem, User
from app.services.paper_ideas import (
    generate_paper_ideas,
    load_idea_papers_for_user,
    validate_idea_sources,
)

router = APIRouter(prefix="/papers", tags=["ideas"])

DEFAULT_USER_EMAIL = "local@papertrail.dev"


class IdeaGenerationRequest(BaseModel):
    paper_ids: list[str] | None = None
    topic: str | None = None


class SelectedIdeaPaperResponse(BaseModel):
    id: str
    title: str
    authors: str | None
    arxiv_url: str | None
    created_at: str


class IdeaResponse(BaseModel):
    title: str
    transformation_type: Literal["combine", "ablate", "extend", "apply"]
    description: str
    why_interesting: str
    feasibility: Literal["low", "medium", "high"]
    evidence_basis: list[str]
    risks_or_unknowns: list[str]
    warnings: list[str]


class IdeaGenerationResponse(BaseModel):
    selected_papers: list[SelectedIdeaPaperResponse]
    source_topic: str | None
    ideas: list[IdeaResponse]
    warnings: list[str]


class SaveIdeasRequest(BaseModel):
    title: str
    paper_ids: list[str] | None = None
    idea_result: IdeaGenerationResponse


class SaveIdeasResponse(BaseModel):
    id: str
    title: str
    item_type: Literal["idea"]
    paper_ids: list[str]
    created_at: str


def _get_or_create_default_user(db: Session) -> User:
    user = db.query(User).filter(User.email == DEFAULT_USER_EMAIL).first()
    if not user:
        user = User(email=DEFAULT_USER_EMAIL, name="Local User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _normalize_idea_title(title: str) -> str:
    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(status_code=400, detail="Idea title is required.")
    if len(normalized_title) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Idea title must be 1000 characters or fewer.",
        )
    return normalized_title


def _validate_idea_result_matches_selected_papers(
    idea_result: IdeaGenerationResponse,
    expected_paper_ids: list[str],
):
    result_paper_ids = [paper.id for paper in idea_result.selected_papers]
    if result_paper_ids != expected_paper_ids:
        raise HTTPException(
            status_code=400,
            detail="Idea payload does not match the selected paper IDs.",
        )


@router.post("/ideas", response_model=IdeaGenerationResponse)
def generate_ideas_endpoint(
    req: IdeaGenerationRequest,
    db: Session = Depends(get_db),
):
    user = _get_or_create_default_user(db)
    try:
        return generate_paper_ideas(
            db=db,
            user_id=uuid.UUID(str(user.id)),
            paper_ids=req.paper_ids,
            topic=req.topic,
        )
    except Exception as error:
        mapped_error = get_provider_error_response(error)
        if mapped_error:
            status_code, detail = mapped_error
            raise HTTPException(status_code=status_code, detail=detail) from error
        raise


@router.post("/ideas/save", response_model=SaveIdeasResponse)
def save_ideas_endpoint(
    req: SaveIdeasRequest,
    db: Session = Depends(get_db),
):
    user = _get_or_create_default_user(db)
    normalized_title = _normalize_idea_title(req.title)
    normalized_ids, normalized_topic = validate_idea_sources(
        req.paper_ids or [],
        req.idea_result.source_topic,
    )
    papers = load_idea_papers_for_user(db, uuid.UUID(str(user.id)), normalized_ids)
    ordered_paper_ids = [str(paper.id) for paper in papers]
    _validate_idea_result_matches_selected_papers(
        req.idea_result,
        ordered_paper_ids,
    )

    data = req.idea_result.model_dump(mode="json")
    data["source_topic"] = normalized_topic

    saved_item = SavedItem(
        user_id=user.id,
        item_type="idea",
        title=normalized_title,
        data=data,
        paper_ids=ordered_paper_ids,
    )
    db.add(saved_item)
    db.commit()
    db.refresh(saved_item)

    return {
        "id": str(saved_item.id),
        "title": saved_item.title,
        "item_type": "idea",
        "paper_ids": ordered_paper_ids,
        "created_at": saved_item.created_at.isoformat() if saved_item.created_at else "",
    }
