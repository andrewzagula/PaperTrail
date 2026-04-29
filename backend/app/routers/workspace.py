import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import DiscoveryRun, Paper, SavedItem, User
from app.services.paper_embeddings import get_paper_embedding_status_map

router = APIRouter(prefix="/workspace", tags=["workspace"])

DEFAULT_USER_EMAIL = "local@papertrail.dev"
RECENT_WORKSPACE_LIMIT = 5
SUPPORTED_SAVED_ITEM_TYPES = {"comparison", "idea", "implementation"}


class WorkspaceCountsResponse(BaseModel):
    papers: int
    discovery_runs: int
    saved_items: int
    saved_comparisons: int
    saved_ideas: int
    saved_implementations: int


class WorkspacePaperResponse(BaseModel):
    id: str
    title: str
    authors: str | None
    abstract: str | None
    arxiv_url: str | None
    created_at: str
    has_structured_breakdown: bool
    embedding_status: str
    embedding_provider: str
    embedding_model: str
    embedded_at: str | None


class WorkspaceDiscoveryRunResponse(BaseModel):
    id: str
    question: str
    status: str
    created_at: str
    num_results: int


class WorkspaceSourcePaperResponse(BaseModel):
    id: str
    title: str
    authors: str | None
    arxiv_url: str | None
    created_at: str


class WorkspaceSavedItemResponse(BaseModel):
    id: str
    title: str
    item_type: str
    paper_ids: list[str]
    created_at: str
    source_papers: list[WorkspaceSourcePaperResponse]


class WorkspaceSavedItemDetailResponse(WorkspaceSavedItemResponse):
    data: dict


class WorkspaceSummaryResponse(BaseModel):
    counts: WorkspaceCountsResponse
    recent_papers: list[WorkspacePaperResponse]
    recent_discovery_runs: list[WorkspaceDiscoveryRunResponse]
    recent_saved_items: list[WorkspaceSavedItemResponse]


class RenameSavedItemRequest(BaseModel):
    title: str


def _get_or_create_default_user(db: Session) -> User:
    user = db.query(User).filter(User.email == DEFAULT_USER_EMAIL).first()
    if not user:
        user = User(email=DEFAULT_USER_EMAIL, name="Local User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _parse_saved_item_id(item_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid saved item ID")


def _validate_saved_item_type(item_type: str | None) -> str | None:
    if item_type is None:
        return None
    if item_type not in SUPPORTED_SAVED_ITEM_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported saved item type")
    return item_type


def _normalize_saved_item_title(title: str) -> str:
    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(status_code=400, detail="Saved item title is required.")
    if len(normalized_title) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Saved item title must be 1000 characters or fewer.",
        )
    return normalized_title


def _get_saved_item_for_user(
    db: Session,
    user_id: uuid.UUID,
    item_id: str,
) -> SavedItem:
    saved_item_id = _parse_saved_item_id(item_id)
    saved_item = (
        db.query(SavedItem)
        .filter(SavedItem.id == saved_item_id, SavedItem.user_id == user_id)
        .first()
    )
    if not saved_item:
        raise HTTPException(status_code=404, detail="Saved item not found")
    return saved_item


def _coerce_paper_ids(paper_ids: list | None) -> list[str]:
    coerced_ids: list[str] = []
    for paper_id in paper_ids or []:
        try:
            coerced_ids.append(str(uuid.UUID(str(paper_id))))
        except ValueError:
            continue
    return coerced_ids


def _load_source_papers(
    db: Session,
    user_id: uuid.UUID,
    saved_items: list[SavedItem],
) -> dict[str, WorkspaceSourcePaperResponse]:
    paper_ids: list[uuid.UUID] = []
    for saved_item in saved_items:
        for paper_id in _coerce_paper_ids(saved_item.paper_ids):
            paper_ids.append(uuid.UUID(paper_id))

    if not paper_ids:
        return {}

    papers = (
        db.query(Paper)
        .filter(Paper.user_id == user_id, Paper.id.in_(paper_ids))
        .all()
    )
    return {
        str(paper.id): WorkspaceSourcePaperResponse(
            id=str(paper.id),
            title=paper.title,
            authors=paper.authors,
            arxiv_url=paper.arxiv_url,
            created_at=paper.created_at.isoformat() if paper.created_at else "",
        )
        for paper in papers
    }


def _saved_item_to_response(
    saved_item: SavedItem,
    source_paper_map: dict[str, WorkspaceSourcePaperResponse],
) -> WorkspaceSavedItemResponse:
    paper_ids = _coerce_paper_ids(saved_item.paper_ids)
    return WorkspaceSavedItemResponse(
        id=str(saved_item.id),
        title=saved_item.title,
        item_type=saved_item.item_type,
        paper_ids=paper_ids,
        created_at=saved_item.created_at.isoformat() if saved_item.created_at else "",
        source_papers=[
            source_paper_map[paper_id]
            for paper_id in paper_ids
            if paper_id in source_paper_map
        ],
    )


def _saved_item_to_detail_response(
    saved_item: SavedItem,
    source_paper_map: dict[str, WorkspaceSourcePaperResponse],
) -> WorkspaceSavedItemDetailResponse:
    base_response = _saved_item_to_response(saved_item, source_paper_map)
    return WorkspaceSavedItemDetailResponse(
        **base_response.model_dump(),
        data=saved_item.data,
    )


def _paper_to_response(
    paper: Paper,
    embedding_fields: dict,
) -> WorkspacePaperResponse:
    return WorkspacePaperResponse(
        id=str(paper.id),
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        arxiv_url=paper.arxiv_url,
        created_at=paper.created_at.isoformat() if paper.created_at else "",
        has_structured_breakdown=bool(paper.structured_breakdown),
        **embedding_fields,
    )


def _discovery_run_to_response(run: DiscoveryRun) -> WorkspaceDiscoveryRunResponse:
    return WorkspaceDiscoveryRunResponse(
        id=str(run.id),
        question=run.question,
        status=run.status,
        created_at=run.created_at.isoformat() if run.created_at else "",
        num_results=len(run.results),
    )


@router.get("/summary", response_model=WorkspaceSummaryResponse)
def get_workspace_summary(db: Session = Depends(get_db)):
    user = _get_or_create_default_user(db)

    saved_items_query = db.query(SavedItem).filter(SavedItem.user_id == user.id)
    counts = WorkspaceCountsResponse(
        papers=db.query(Paper).filter(Paper.user_id == user.id).count(),
        discovery_runs=(
            db.query(DiscoveryRun).filter(DiscoveryRun.user_id == user.id).count()
        ),
        saved_items=saved_items_query.count(),
        saved_comparisons=saved_items_query.filter(
            SavedItem.item_type == "comparison"
        ).count(),
        saved_ideas=saved_items_query.filter(SavedItem.item_type == "idea").count(),
        saved_implementations=saved_items_query.filter(
            SavedItem.item_type == "implementation"
        ).count(),
    )

    recent_papers = (
        db.query(Paper)
        .filter(Paper.user_id == user.id)
        .order_by(Paper.created_at.desc())
        .limit(RECENT_WORKSPACE_LIMIT)
        .all()
    )
    embedding_status_map = get_paper_embedding_status_map(
        db,
        [paper.id for paper in recent_papers],
    )

    recent_discovery_runs = (
        db.query(DiscoveryRun)
        .filter(DiscoveryRun.user_id == user.id)
        .order_by(DiscoveryRun.created_at.desc())
        .limit(RECENT_WORKSPACE_LIMIT)
        .all()
    )
    recent_saved_items = (
        saved_items_query.order_by(SavedItem.created_at.desc())
        .limit(RECENT_WORKSPACE_LIMIT)
        .all()
    )
    source_paper_map = _load_source_papers(db, user.id, recent_saved_items)

    return WorkspaceSummaryResponse(
        counts=counts,
        recent_papers=[
            _paper_to_response(
                paper,
                embedding_status_map[str(paper.id)].to_response_fields(),
            )
            for paper in recent_papers
        ],
        recent_discovery_runs=[
            _discovery_run_to_response(run) for run in recent_discovery_runs
        ],
        recent_saved_items=[
            _saved_item_to_response(saved_item, source_paper_map)
            for saved_item in recent_saved_items
        ],
    )


@router.get("/saved-items", response_model=list[WorkspaceSavedItemResponse])
def list_workspace_saved_items(
    item_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    user = _get_or_create_default_user(db)
    normalized_item_type = _validate_saved_item_type(item_type)

    query = db.query(SavedItem).filter(SavedItem.user_id == user.id)
    if normalized_item_type:
        query = query.filter(SavedItem.item_type == normalized_item_type)

    saved_items = query.order_by(SavedItem.created_at.desc()).all()
    source_paper_map = _load_source_papers(db, user.id, saved_items)
    return [
        _saved_item_to_response(saved_item, source_paper_map)
        for saved_item in saved_items
    ]


@router.get(
    "/saved-items/{item_id}",
    response_model=WorkspaceSavedItemDetailResponse,
)
def get_workspace_saved_item(item_id: str, db: Session = Depends(get_db)):
    user = _get_or_create_default_user(db)
    saved_item = _get_saved_item_for_user(db, user.id, item_id)
    source_paper_map = _load_source_papers(db, user.id, [saved_item])
    return _saved_item_to_detail_response(saved_item, source_paper_map)


@router.patch(
    "/saved-items/{item_id}",
    response_model=WorkspaceSavedItemResponse,
)
def rename_workspace_saved_item(
    item_id: str,
    req: RenameSavedItemRequest,
    db: Session = Depends(get_db),
):
    user = _get_or_create_default_user(db)
    saved_item = _get_saved_item_for_user(db, user.id, item_id)
    saved_item.title = _normalize_saved_item_title(req.title)
    db.commit()
    db.refresh(saved_item)

    source_paper_map = _load_source_papers(db, user.id, [saved_item])
    return _saved_item_to_response(saved_item, source_paper_map)


@router.delete("/saved-items/{item_id}")
def delete_workspace_saved_item(item_id: str, db: Session = Depends(get_db)):
    user = _get_or_create_default_user(db)
    saved_item = _get_saved_item_for_user(db, user.id, item_id)
    saved_item_id = str(saved_item.id)

    db.delete(saved_item)
    db.commit()

    return {"status": "deleted", "id": saved_item_id}
