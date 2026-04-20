from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import PaperEmbeddingState
from app.services.embedder import embed_and_store_sections
from app.services.vector_store import (
    delete_by_paper_from_active_collection,
    get_active_collection_name,
)

EMBEDDING_STATUS_READY = "ready"
EMBEDDING_STATUS_FAILED = "failed"
EMBEDDING_STATUS_STALE = "stale"
EMBEDDING_STATUS_MISSING = "missing"


@dataclass(frozen=True)
class ActiveEmbeddingStatus:
    status: str
    embedding_provider: str
    embedding_model: str
    embedded_at: datetime | None

    def to_response_fields(self) -> dict:
        return {
            "embedding_status": self.status,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedded_at": self.embedded_at.isoformat() if self.embedded_at else None,
        }


def _coerce_paper_id(paper_id: uuid.UUID | str) -> uuid.UUID:
    if isinstance(paper_id, uuid.UUID):
        return paper_id
    return uuid.UUID(str(paper_id))


def get_active_embedding_identity() -> tuple[str, str, str]:
    return (
        settings.embedding_provider,
        settings.embedding_model,
        get_active_collection_name(),
    )


def upsert_active_embedding_state(
    db: Session,
    paper_id: uuid.UUID | str,
    *,
    status: str,
    chunk_count: int,
    last_error: str | None = None,
) -> PaperEmbeddingState:
    paper_uuid = _coerce_paper_id(paper_id)
    provider, model, collection_name = get_active_embedding_identity()
    state = (
        db.query(PaperEmbeddingState)
        .filter(
            PaperEmbeddingState.paper_id == paper_uuid,
            PaperEmbeddingState.embedding_provider == provider,
            PaperEmbeddingState.embedding_model == model,
        )
        .first()
    )
    if not state:
        state = PaperEmbeddingState(
            paper_id=paper_uuid,
            embedding_provider=provider,
            embedding_model=model,
            collection_name=collection_name,
        )
        db.add(state)

    state.collection_name = collection_name
    state.chunk_count = chunk_count
    state.status = status
    state.last_error = last_error
    state.embedded_at = (
        datetime.now(timezone.utc) if status == EMBEDDING_STATUS_READY else None
    )
    db.flush()
    return state


def derive_active_embedding_status(
    states: Iterable[PaperEmbeddingState],
) -> ActiveEmbeddingStatus:
    provider, model, _ = get_active_embedding_identity()
    states_list = list(states)
    active_state = next(
        (
            state
            for state in states_list
            if state.embedding_provider == provider and state.embedding_model == model
        ),
        None,
    )
    if active_state:
        if active_state.status == EMBEDDING_STATUS_READY:
            return ActiveEmbeddingStatus(
                status=EMBEDDING_STATUS_READY,
                embedding_provider=provider,
                embedding_model=model,
                embedded_at=active_state.embedded_at,
            )
        return ActiveEmbeddingStatus(
            status=EMBEDDING_STATUS_FAILED,
            embedding_provider=provider,
            embedding_model=model,
            embedded_at=None,
        )

    if any(state.status == EMBEDDING_STATUS_READY for state in states_list):
        return ActiveEmbeddingStatus(
            status=EMBEDDING_STATUS_STALE,
            embedding_provider=provider,
            embedding_model=model,
            embedded_at=None,
        )

    return ActiveEmbeddingStatus(
        status=EMBEDDING_STATUS_MISSING,
        embedding_provider=provider,
        embedding_model=model,
        embedded_at=None,
    )


def get_paper_embedding_status(db: Session, paper_id: uuid.UUID | str) -> ActiveEmbeddingStatus:
    paper_uuid = _coerce_paper_id(paper_id)
    states = (
        db.query(PaperEmbeddingState)
        .filter(PaperEmbeddingState.paper_id == paper_uuid)
        .all()
    )
    return derive_active_embedding_status(states)


def get_paper_embedding_status_map(
    db: Session,
    paper_ids: Iterable[uuid.UUID | str],
) -> dict[str, ActiveEmbeddingStatus]:
    paper_uuid_map: dict[str, uuid.UUID] = {}
    for paper_id in paper_ids:
        paper_uuid = _coerce_paper_id(paper_id)
        paper_uuid_map[str(paper_uuid)] = paper_uuid

    if not paper_uuid_map:
        return {}

    states = (
        db.query(PaperEmbeddingState)
        .filter(PaperEmbeddingState.paper_id.in_(list(paper_uuid_map.values())))
        .all()
    )
    state_map: dict[str, list[PaperEmbeddingState]] = {
        paper_id: [] for paper_id in paper_uuid_map
    }
    for state in states:
        state_map[str(state.paper_id)].append(state)

    return {
        paper_id: derive_active_embedding_status(state_map[paper_id])
        for paper_id in state_map
    }


def sync_paper_embeddings(
    db: Session,
    paper_id: uuid.UUID | str,
    sections: list[dict],
    *,
    replace_active_embeddings: bool = False,
) -> int:
    paper_uuid = _coerce_paper_id(paper_id)
    paper_id_str = str(paper_uuid)

    try:
        if replace_active_embeddings:
            delete_by_paper_from_active_collection(paper_id_str)

        chunk_count = embed_and_store_sections(
            paper_id=paper_id_str,
            sections=sections,
        )
    except Exception as error:
        upsert_active_embedding_state(
            db,
            paper_uuid,
            status=EMBEDDING_STATUS_FAILED,
            chunk_count=0,
            last_error=str(error),
        )
        db.commit()
        raise

    upsert_active_embedding_state(
        db,
        paper_uuid,
        status=EMBEDDING_STATUS_READY,
        chunk_count=chunk_count,
        last_error=None,
    )
    db.commit()
    return chunk_count
