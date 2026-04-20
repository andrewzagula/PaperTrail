import uuid
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.models import Paper, PaperEmbeddingState, PaperSection, User
from app.services.paper_embeddings import (
    EMBEDDING_STATUS_FAILED,
    EMBEDDING_STATUS_MISSING,
    EMBEDDING_STATUS_READY,
    EMBEDDING_STATUS_STALE,
    derive_active_embedding_status,
    get_paper_embedding_status,
    sync_paper_embeddings,
)


class PaperEmbeddingServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_local = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _create_paper(self, title: str = "Test Paper") -> str:
        with self.session_local() as db:
            user = User(email=f"{title.lower().replace(' ', '_')}@example.com", name="User")
            db.add(user)
            db.flush()

            paper = Paper(
                user_id=user.id,
                title=title,
                authors="Author",
                abstract="Abstract",
                raw_text="Raw text",
            )
            db.add(paper)
            db.flush()

            db.add(
                PaperSection(
                    paper_id=paper.id,
                    section_title="Method",
                    section_order=0,
                    content="Method section content",
                )
            )
            db.commit()
            return str(paper.id)

    def test_derive_active_embedding_status_covers_ready_failed_stale_and_missing(self):
        ready_state = PaperEmbeddingState(
            paper_id=uuid.uuid4(),
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            collection_name="paper_sections__openai__ready",
            chunk_count=2,
            status=EMBEDDING_STATUS_READY,
            embedded_at=datetime.now(timezone.utc),
        )
        failed_state = PaperEmbeddingState(
            paper_id=uuid.uuid4(),
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            collection_name="paper_sections__openai__failed",
            chunk_count=0,
            status=EMBEDDING_STATUS_FAILED,
        )
        stale_state = PaperEmbeddingState(
            paper_id=uuid.uuid4(),
            embedding_provider="sentence_transformers",
            embedding_model="all-MiniLM-L6-v2",
            collection_name="paper_sections__local__stale",
            chunk_count=2,
            status=EMBEDDING_STATUS_READY,
        )

        self.assertEqual(derive_active_embedding_status([ready_state]).status, "ready")
        self.assertEqual(derive_active_embedding_status([failed_state]).status, "failed")
        self.assertEqual(derive_active_embedding_status([stale_state]).status, "stale")
        self.assertEqual(derive_active_embedding_status([]).status, "missing")

    def test_sync_paper_embeddings_records_ready_state(self):
        paper_id = self._create_paper()
        sections = [
            {
                "id": str(uuid.uuid4()),
                "title": "Method",
                "content": "Method section content",
            }
        ]

        with self.session_local() as db, patch(
            "app.services.paper_embeddings.embed_and_store_sections",
            return_value=4,
        ):
            chunk_count = sync_paper_embeddings(db, paper_id, sections)

        self.assertEqual(chunk_count, 4)

        with self.session_local() as db:
            status = get_paper_embedding_status(db, paper_id)
            self.assertEqual(status.status, EMBEDDING_STATUS_READY)
            state = db.query(PaperEmbeddingState).filter_by(paper_id=uuid.UUID(paper_id)).one()
            self.assertEqual(state.chunk_count, 4)
            self.assertIsNone(state.last_error)
            self.assertIsNotNone(state.embedded_at)

    def test_sync_paper_embeddings_records_failed_state_and_reraises(self):
        paper_id = self._create_paper("Broken Paper")
        sections = [
            {
                "id": str(uuid.uuid4()),
                "title": "Method",
                "content": "Method section content",
            }
        ]

        with self.session_local() as db, patch(
            "app.services.paper_embeddings.embed_and_store_sections",
            side_effect=RuntimeError("embedding backend failed"),
        ):
            with self.assertRaises(RuntimeError):
                sync_paper_embeddings(db, paper_id, sections, replace_active_embeddings=True)

        with self.session_local() as db:
            status = get_paper_embedding_status(db, paper_id)
            self.assertEqual(status.status, EMBEDDING_STATUS_FAILED)
            state = db.query(PaperEmbeddingState).filter_by(paper_id=uuid.UUID(paper_id)).one()
            self.assertEqual(state.chunk_count, 0)
            self.assertIn("embedding backend failed", state.last_error or "")
            self.assertIsNone(state.embedded_at)

    def test_get_paper_embedding_status_returns_missing_when_no_rows_exist(self):
        paper_id = self._create_paper("Missing Paper")

        with self.session_local() as db:
            status = get_paper_embedding_status(db, paper_id)

        self.assertEqual(status.status, EMBEDDING_STATUS_MISSING)


if __name__ == "__main__":
    unittest.main()
