import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm import get_provider_error_response
from app.models.models import SavedItem, User
from app.services.paper_implementation import (
    generate_paper_implementation,
    load_implementation_paper_for_user,
    validate_implementation_paper_id,
)

router = APIRouter(prefix="/papers", tags=["implementations"])

DEFAULT_USER_EMAIL = "local@papertrail.dev"


class ImplementationRequest(BaseModel):
    focus: str | None = None
    target_language: str = "python"
    target_framework: str = "pytorch"


class ImplementationPaperResponse(BaseModel):
    id: str
    title: str
    authors: str | None
    arxiv_url: str | None
    created_at: str


class ImplementationSourceSectionResponse(BaseModel):
    id: str
    title: str
    section_order: int
    content_preview: str


class AlgorithmStepResponse(BaseModel):
    order: int
    title: str
    description: str
    inputs: list[str]
    outputs: list[str]
    evidence: list[str]


class AssumptionGapResponse(BaseModel):
    category: str
    description: str
    severity: Literal["low", "medium", "high"]
    evidence: list[str]


class StarterCodeFileResponse(BaseModel):
    path: str
    language: str
    purpose: str
    content: str


class ImplementationResponse(BaseModel):
    paper: ImplementationPaperResponse
    source_sections: list[ImplementationSourceSectionResponse]
    implementation_summary: str
    algorithm_steps: list[AlgorithmStepResponse]
    assumptions_and_gaps: list[AssumptionGapResponse]
    pseudocode: str
    starter_code: list[StarterCodeFileResponse]
    setup_notes: list[str]
    test_plan: list[str]
    warnings: list[str]


class SaveImplementationRequest(BaseModel):
    title: str
    implementation: ImplementationResponse


class SaveImplementationResponse(BaseModel):
    id: str
    title: str
    item_type: Literal["implementation"]
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


def _normalize_implementation_title(title: str) -> str:
    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(
            status_code=400,
            detail="Implementation title is required.",
        )
    if len(normalized_title) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Implementation title must be 1000 characters or fewer.",
        )
    return normalized_title


def _validate_implementation_result_matches_paper(
    implementation: ImplementationResponse,
    expected_paper_id: str,
    expected_paper_title: str,
):
    if (
        implementation.paper.id != expected_paper_id
        or implementation.paper.title != expected_paper_title
    ):
        raise HTTPException(
            status_code=400,
            detail="Implementation payload does not match the selected paper.",
        )


@router.post("/{paper_id}/implement", response_model=ImplementationResponse)
def generate_implementation_endpoint(
    paper_id: str,
    req: ImplementationRequest,
    db: Session = Depends(get_db),
):
    user = _get_or_create_default_user(db)
    try:
        return generate_paper_implementation(
            db=db,
            user_id=uuid.UUID(str(user.id)),
            paper_id=paper_id,
            focus=req.focus,
            target_language=req.target_language,
            target_framework=req.target_framework,
        )
    except Exception as error:
        mapped_error = get_provider_error_response(error)
        if mapped_error:
            status_code, detail = mapped_error
            raise HTTPException(status_code=status_code, detail=detail) from error
        raise


@router.post("/{paper_id}/implement/save", response_model=SaveImplementationResponse)
def save_implementation_endpoint(
    paper_id: str,
    req: SaveImplementationRequest,
    db: Session = Depends(get_db),
):
    user = _get_or_create_default_user(db)
    normalized_paper_id = validate_implementation_paper_id(paper_id)
    paper = load_implementation_paper_for_user(
        db,
        uuid.UUID(str(user.id)),
        normalized_paper_id,
    )
    normalized_title = _normalize_implementation_title(req.title)
    paper_id_string = str(paper.id)
    _validate_implementation_result_matches_paper(
        req.implementation,
        paper_id_string,
        paper.title,
    )

    saved_item = SavedItem(
        user_id=user.id,
        item_type="implementation",
        title=normalized_title,
        data=req.implementation.model_dump(mode="json"),
        paper_ids=[paper_id_string],
    )
    db.add(saved_item)
    db.commit()
    db.refresh(saved_item)

    return {
        "id": str(saved_item.id),
        "title": saved_item.title,
        "item_type": "implementation",
        "paper_ids": [paper_id_string],
        "created_at": saved_item.created_at.isoformat() if saved_item.created_at else "",
    }
