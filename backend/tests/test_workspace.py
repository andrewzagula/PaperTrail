import uuid
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.models import (
    DiscoveryResult,
    DiscoveryRun,
    Paper,
    PaperEmbeddingState,
    PaperSection,
    SavedItem,
    User,
)
from app.services.paper_embeddings import EMBEDDING_STATUS_READY
from app.services.vector_store import get_active_collection_name

DEFAULT_USER_EMAIL = "local@papertrail.dev"


class WorkspaceEndpointTests(unittest.TestCase):
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

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.init_db_patch = patch("app.main.init_db", return_value=None)
        self.init_db_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.init_db_patch.stop()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _get_or_create_user(self, email: str = DEFAULT_USER_EMAIL) -> uuid.UUID:
        with self.session_local() as db:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(email=email, name="Local User")
                db.add(user)
                db.commit()
                db.refresh(user)
            return uuid.UUID(str(user.id))

    def _create_paper(
        self,
        title: str,
        *,
        user_email: str = DEFAULT_USER_EMAIL,
        created_at: datetime | None = None,
        with_breakdown: bool = False,
        with_ready_embedding: bool = False,
    ) -> str:
        user_id = self._get_or_create_user(user_email)
        with self.session_local() as db:
            paper = Paper(
                user_id=user_id,
                title=title,
                authors=f"{title} Authors",
                abstract=f"{title} abstract",
                arxiv_url=f"https://arxiv.org/abs/{title.replace(' ', '_')}",
                pdf_path=f"/tmp/{title.replace(' ', '_')}.pdf",
                raw_text=f"{title} raw text",
                structured_breakdown=(
                    {"problem": f"{title} problem"} if with_breakdown else None
                ),
                created_at=created_at,
            )
            db.add(paper)
            db.flush()
            db.add(
                PaperSection(
                    paper_id=paper.id,
                    section_title="Method",
                    section_order=0,
                    content=f"{title} method section",
                )
            )
            if with_ready_embedding:
                db.add(
                    PaperEmbeddingState(
                        paper_id=paper.id,
                        embedding_provider=settings.embedding_provider,
                        embedding_model=settings.embedding_model,
                        collection_name=get_active_collection_name(),
                        chunk_count=1,
                        status=EMBEDDING_STATUS_READY,
                        embedded_at=datetime(2026, 4, 28, tzinfo=timezone.utc),
                    )
                )
            db.commit()
            db.refresh(paper)
            return str(paper.id)

    def _create_discovery_run(
        self,
        question: str,
        *,
        user_email: str = DEFAULT_USER_EMAIL,
        created_at: datetime | None = None,
        result_count: int = 0,
        status: str = "complete",
    ) -> str:
        user_id = self._get_or_create_user(user_email)
        with self.session_local() as db:
            run = DiscoveryRun(
                user_id=user_id,
                question=question,
                status=status,
                generated_queries=[question],
                created_at=created_at,
            )
            db.add(run)
            db.flush()
            for index in range(result_count):
                db.add(
                    DiscoveryResult(
                        run_id=run.id,
                        arxiv_id=f"2604.{index:05d}",
                        title=f"{question} Result {index}",
                        authors="Researcher",
                        abstract="Abstract",
                        published="2026-04-28",
                        relevance_score=0.9,
                        relevance_reason="Relevant",
                        rank_order=index + 1,
                    )
                )
            db.commit()
            db.refresh(run)
            return str(run.id)

    def _create_saved_item(
        self,
        title: str,
        item_type: str,
        *,
        paper_ids: list[str] | None = None,
        user_email: str = DEFAULT_USER_EMAIL,
        created_at: datetime | None = None,
        data: dict | None = None,
    ) -> str:
        user_id = self._get_or_create_user(user_email)
        with self.session_local() as db:
            saved_item = SavedItem(
                user_id=user_id,
                item_type=item_type,
                title=title,
                data=data or {"title": title, "item_type": item_type},
                paper_ids=paper_ids or [],
                created_at=created_at,
            )
            db.add(saved_item)
            db.commit()
            db.refresh(saved_item)
            return str(saved_item.id)

    def _saved_item_exists(self, saved_item_id: str) -> bool:
        with self.session_local() as db:
            return (
                db.query(SavedItem)
                .filter(SavedItem.id == uuid.UUID(saved_item_id))
                .first()
                is not None
            )

    def _paper_exists(self, paper_id: str) -> bool:
        with self.session_local() as db:
            return (
                db.query(Paper).filter(Paper.id == uuid.UUID(paper_id)).first()
                is not None
            )

    def test_summary_returns_empty_workspace_for_clean_database(self):
        response = self.client.get("/workspace/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["counts"],
            {
                "papers": 0,
                "discovery_runs": 0,
                "saved_items": 0,
                "saved_comparisons": 0,
                "saved_ideas": 0,
                "saved_implementations": 0,
            },
        )
        self.assertEqual(payload["recent_papers"], [])
        self.assertEqual(payload["recent_discovery_runs"], [])
        self.assertEqual(payload["recent_saved_items"], [])

    def test_summary_counts_recent_items_and_exposes_paper_metadata(self):
        old_paper_id = self._create_paper(
            "Old Paper",
            created_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
        )
        ready_paper_id = self._create_paper(
            "Ready Paper",
            created_at=datetime(2026, 4, 28, tzinfo=timezone.utc),
            with_breakdown=True,
            with_ready_embedding=True,
        )
        self._create_paper(
            "Other User Paper",
            user_email="other@papertrail.dev",
            created_at=datetime(2026, 4, 29, tzinfo=timezone.utc),
        )
        self._create_discovery_run(
            "long-context retrieval",
            created_at=datetime(2026, 4, 28, 1, tzinfo=timezone.utc),
            result_count=2,
        )
        self._create_discovery_run(
            "other user discovery",
            user_email="other@papertrail.dev",
            created_at=datetime(2026, 4, 29, tzinfo=timezone.utc),
            result_count=3,
        )
        self._create_saved_item(
            "Comparison",
            "comparison",
            paper_ids=[old_paper_id, ready_paper_id],
            created_at=datetime(2026, 4, 28, 2, tzinfo=timezone.utc),
        )
        self._create_saved_item(
            "Ideas",
            "idea",
            paper_ids=[ready_paper_id],
            created_at=datetime(2026, 4, 28, 3, tzinfo=timezone.utc),
        )
        self._create_saved_item(
            "Implementation",
            "implementation",
            paper_ids=[ready_paper_id],
            created_at=datetime(2026, 4, 28, 4, tzinfo=timezone.utc),
        )
        self._create_saved_item(
            "Legacy",
            "legacy",
            created_at=datetime(2026, 4, 28, 5, tzinfo=timezone.utc),
        )
        self._create_saved_item(
            "Other User Saved Item",
            "idea",
            user_email="other@papertrail.dev",
            created_at=datetime(2026, 4, 29, tzinfo=timezone.utc),
        )

        response = self.client.get("/workspace/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["counts"]["papers"], 2)
        self.assertEqual(payload["counts"]["discovery_runs"], 1)
        self.assertEqual(payload["counts"]["saved_items"], 4)
        self.assertEqual(payload["counts"]["saved_comparisons"], 1)
        self.assertEqual(payload["counts"]["saved_ideas"], 1)
        self.assertEqual(payload["counts"]["saved_implementations"], 1)

        self.assertEqual(payload["recent_papers"][0]["title"], "Ready Paper")
        self.assertTrue(payload["recent_papers"][0]["has_structured_breakdown"])
        self.assertEqual(payload["recent_papers"][0]["embedding_status"], "ready")
        self.assertEqual(payload["recent_papers"][1]["title"], "Old Paper")
        self.assertEqual(payload["recent_papers"][1]["embedding_status"], "missing")

        self.assertEqual(
            payload["recent_discovery_runs"][0]["question"],
            "long-context retrieval",
        )
        self.assertEqual(payload["recent_discovery_runs"][0]["num_results"], 2)

        self.assertEqual(payload["recent_saved_items"][0]["title"], "Legacy")
        comparison = next(
            item
            for item in payload["recent_saved_items"]
            if item["title"] == "Comparison"
        )
        self.assertEqual(
            [paper["id"] for paper in comparison["source_papers"]],
            [old_paper_id, ready_paper_id],
        )

    def test_list_saved_items_is_newest_first_without_data(self):
        old_id = self._create_saved_item(
            "Old Comparison",
            "comparison",
            created_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
            data={"secret": "old payload"},
        )
        new_id = self._create_saved_item(
            "New Idea",
            "idea",
            created_at=datetime(2026, 4, 28, tzinfo=timezone.utc),
            data={"secret": "new payload"},
        )

        response = self.client.get("/workspace/saved-items")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["id"] for item in payload], [new_id, old_id])
        self.assertNotIn("data", payload[0])
        self.assertNotIn("data", payload[1])

    def test_list_saved_items_filters_by_type(self):
        self._create_saved_item("Comparison", "comparison")
        idea_id = self._create_saved_item("Idea", "idea")
        self._create_saved_item("Implementation", "implementation")

        response = self.client.get("/workspace/saved-items?item_type=idea")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], idea_id)
        self.assertEqual(payload[0]["item_type"], "idea")

    def test_list_saved_items_rejects_unsupported_type_filter(self):
        response = self.client.get("/workspace/saved-items?item_type=legacy")

        self.assertEqual(response.status_code, 400)

    def test_saved_item_detail_returns_full_data_unchanged(self):
        paper_id = self._create_paper("Source Paper")
        saved_payload = {
            "selected_papers": [{"id": paper_id, "title": "Source Paper"}],
            "nested": {"warnings": ["keep exact payload"]},
        }
        saved_item_id = self._create_saved_item(
            "Detailed Comparison",
            "comparison",
            paper_ids=[paper_id],
            data=saved_payload,
        )

        response = self.client.get(f"/workspace/saved-items/{saved_item_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"], saved_payload)
        self.assertEqual(payload["source_papers"][0]["id"], paper_id)

    def test_saved_item_detail_validates_id_and_missing_item(self):
        invalid_response = self.client.get("/workspace/saved-items/not-a-uuid")
        self.assertEqual(invalid_response.status_code, 400)

        missing_response = self.client.get(f"/workspace/saved-items/{uuid.uuid4()}")
        self.assertEqual(missing_response.status_code, 404)

    def test_rename_saved_item_strips_title(self):
        saved_item_id = self._create_saved_item("Original", "idea")

        response = self.client.patch(
            f"/workspace/saved-items/{saved_item_id}",
            json={"title": "  Renamed Idea  "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Renamed Idea")
        with self.session_local() as db:
            saved_item = (
                db.query(SavedItem)
                .filter(SavedItem.id == uuid.UUID(saved_item_id))
                .first()
            )
            self.assertEqual(saved_item.title, "Renamed Idea")

    def test_rename_saved_item_rejects_blank_and_overlong_titles(self):
        saved_item_id = self._create_saved_item("Original", "idea")

        blank_response = self.client.patch(
            f"/workspace/saved-items/{saved_item_id}",
            json={"title": "   "},
        )
        self.assertEqual(blank_response.status_code, 400)

        overlong_response = self.client.patch(
            f"/workspace/saved-items/{saved_item_id}",
            json={"title": "x" * 1001},
        )
        self.assertEqual(overlong_response.status_code, 400)

    def test_delete_saved_item_does_not_delete_linked_paper(self):
        paper_id = self._create_paper("Source Paper")
        saved_item_id = self._create_saved_item(
            "Implementation",
            "implementation",
            paper_ids=[paper_id],
        )

        response = self.client.delete(f"/workspace/saved-items/{saved_item_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted", "id": saved_item_id})
        self.assertFalse(self._saved_item_exists(saved_item_id))
        self.assertTrue(self._paper_exists(paper_id))

    def test_saved_item_operations_are_scoped_to_default_user(self):
        other_paper_id = self._create_paper(
            "Other Paper",
            user_email="other@papertrail.dev",
        )
        other_saved_item_id = self._create_saved_item(
            "Other User Idea",
            "idea",
            paper_ids=[other_paper_id],
            user_email="other@papertrail.dev",
        )

        list_response = self.client.get("/workspace/saved-items")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json(), [])

        detail_response = self.client.get(
            f"/workspace/saved-items/{other_saved_item_id}"
        )
        self.assertEqual(detail_response.status_code, 404)

        rename_response = self.client.patch(
            f"/workspace/saved-items/{other_saved_item_id}",
            json={"title": "Should Not Rename"},
        )
        self.assertEqual(rename_response.status_code, 404)

        delete_response = self.client.delete(
            f"/workspace/saved-items/{other_saved_item_id}"
        )
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(self._saved_item_exists(other_saved_item_id))


if __name__ == "__main__":
    unittest.main()
