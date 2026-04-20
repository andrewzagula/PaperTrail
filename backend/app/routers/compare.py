import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm import get_provider_error_response
from app.models.models import SavedItem, User
from app.services.paper_compare import (
    compare_papers,
    load_papers_for_user,
    validate_compare_paper_ids,
)

router = APIRouter(prefix="/papers", tags=["compare"])

DEFAULT_USER_EMAIL = "local@papertrail.dev"


class CompareRequest(BaseModel):
    paper_ids: list[str]


class SelectedPaperResponse(BaseModel):
    id: str
    title: str
    authors: str | None
    arxiv_url: str | None
    created_at: str


class NormalizedPaperProfileResponse(BaseModel):
    paper_id: str
    title: str
    authors: str
    problem: str
    method: str
    dataset_or_eval_setup: str
    key_results: str
    strengths: str
    weaknesses: str
    evidence_notes: dict[str, list[str]]
    warnings: list[str]


class ComparisonTableColumnResponse(BaseModel):
    key: str
    label: str


class ComparisonTableRowResponse(BaseModel):
    key: str
    label: str
    values: list[str]


class ComparisonTableResponse(BaseModel):
    columns: list[ComparisonTableColumnResponse]
    rows: list[ComparisonTableRowResponse]


class CompareResponse(BaseModel):
    selected_papers: list[SelectedPaperResponse]
    normalized_profiles: list[NormalizedPaperProfileResponse]
    comparison_table: ComparisonTableResponse
    narrative_summary: str
    warnings: list[str]


class SaveComparisonRequest(BaseModel):
    title: str
    paper_ids: list[str]
    comparison: CompareResponse


class SaveComparisonResponse(BaseModel):
    id: str
    title: str
    item_type: Literal["comparison"]
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


@router.post("/compare", response_model=CompareResponse)
def compare_papers_endpoint(
    req: CompareRequest,
    db: Session = Depends(get_db),
):
    user = _get_or_create_default_user(db)
    try:
        return compare_papers(
            db=db,
            user_id=uuid.UUID(str(user.id)),
            paper_ids=req.paper_ids,
        )
    except Exception as error:
        mapped_error = get_provider_error_response(error)
        if mapped_error:
            status_code, detail = mapped_error
            raise HTTPException(status_code=status_code, detail=detail) from error
        raise


def _normalize_comparison_title(title: str) -> str:
    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(status_code=400, detail="Comparison title is required.")
    if len(normalized_title) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Comparison title must be 1000 characters or fewer.",
        )
    return normalized_title


def _validate_comparison_matches_selected_papers(
    comparison: CompareResponse,
    expected_paper_ids: list[str],
):
    comparison_paper_ids = [paper.id for paper in comparison.selected_papers]
    if comparison_paper_ids != expected_paper_ids:
        raise HTTPException(
            status_code=400,
            detail="Comparison payload does not match the selected paper IDs.",
        )


@router.post("/compare/save", response_model=SaveComparisonResponse)
def save_comparison_endpoint(
    req: SaveComparisonRequest,
    db: Session = Depends(get_db),
):
    user = _get_or_create_default_user(db)
    normalized_title = _normalize_comparison_title(req.title)
    normalized_ids = validate_compare_paper_ids(req.paper_ids)
    papers = load_papers_for_user(db, uuid.UUID(str(user.id)), normalized_ids)
    ordered_paper_ids = [str(paper.id) for paper in papers]
    _validate_comparison_matches_selected_papers(req.comparison, ordered_paper_ids)

    saved_item = SavedItem(
        user_id=user.id,
        item_type="comparison",
        title=normalized_title,
        data=req.comparison.model_dump(mode="json"),
        paper_ids=ordered_paper_ids,
    )
    db.add(saved_item)
    db.commit()
    db.refresh(saved_item)

    return {
        "id": str(saved_item.id),
        "title": saved_item.title,
        "item_type": "comparison",
        "paper_ids": ordered_paper_ids,
        "created_at": saved_item.created_at.isoformat() if saved_item.created_at else "",
    }
