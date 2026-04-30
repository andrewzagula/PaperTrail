import asyncio
import tempfile
import uuid
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.llm.errors import CONFIGURATION_ERROR_DETAIL, MissingProviderCredentialsError
from app.main import app
from app.models.models import Paper, PaperEmbeddingState, PaperSection, User
from app.services.arxiv_fetcher import (
    ARXIV_INVALID_PDF_DETAIL,
    ARXIV_NOT_FOUND_DETAIL,
    ARXIV_UNAVAILABLE_DETAIL,
    download_arxiv_pdf,
    fetch_arxiv_metadata,
)
from app.services.errors import UserSafeServiceError
from app.services.paper_embeddings import (
    EMBEDDING_STATUS_FAILED,
    EMBEDDING_STATUS_READY,
)
from app.services.pdf_parser import PDF_READ_ERROR_DETAIL
from app.services.vector_store import get_active_collection_name

DEFAULT_USER_EMAIL = "local@papertrail.dev"


class PaperEndpointTests(unittest.TestCase):
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
        breakdown: dict | None,
        sections: list[dict] | None = None,
    ) -> str:
        with self.session_local() as db:
            paper = Paper(
                user_id=self._get_or_create_user(),
                title=title,
                authors=f"{title} Authors",
                abstract=f"{title} abstract",
                arxiv_url=f"https://arxiv.org/abs/{title.replace(' ', '_')}",
                pdf_path=f"/tmp/{title.replace(' ', '_')}.pdf",
                raw_text=f"{title} raw text",
                structured_breakdown=breakdown,
            )
            db.add(paper)
            db.flush()

            for index, section in enumerate(
                sections
                or [{"title": "Method", "content": f"{title} section content"}]
            ):
                db.add(
                    PaperSection(
                        paper_id=paper.id,
                        section_title=section["title"],
                        section_order=index,
                        content=section["content"],
                    )
                )

            db.commit()
            db.refresh(paper)
            return str(paper.id)

    def _create_embedding_state(
        self,
        paper_id: str,
        *,
        embedding_provider: str,
        embedding_model: str,
        status: str,
        chunk_count: int = 1,
        collection_name: str | None = None,
    ) -> None:
        with self.session_local() as db:
            db.add(
                PaperEmbeddingState(
                    paper_id=uuid.UUID(paper_id),
                    embedding_provider=embedding_provider,
                    embedding_model=embedding_model,
                    collection_name=collection_name or get_active_collection_name(),
                    chunk_count=chunk_count,
                    status=status,
                )
            )
            db.commit()

    def test_list_and_get_papers_expose_embedding_metadata(self):
        ready_paper_id = self._create_paper(
            "Analyzed Paper",
            breakdown={
                "problem": "Problem",
                "method": "Method",
            },
        )
        missing_paper_id = self._create_paper("Raw Paper", breakdown=None)
        self._create_embedding_state(
            ready_paper_id,
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            status=EMBEDDING_STATUS_READY,
        )

        response = self.client.get("/papers/")

        self.assertEqual(response.status_code, 200)
        payload = {paper["title"]: paper for paper in response.json()}
        self.assertTrue(payload["Analyzed Paper"]["has_structured_breakdown"])
        self.assertEqual(payload["Analyzed Paper"]["embedding_status"], "ready")
        self.assertFalse(payload["Raw Paper"]["has_structured_breakdown"])
        self.assertEqual(payload["Raw Paper"]["embedding_status"], "missing")

        detail_response = self.client.get(f"/papers/{missing_paper_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["embedding_status"], "missing")

    def test_single_reembed_reembeds_stale_paper_and_updates_state(self):
        paper_id = self._create_paper("Stale Paper", breakdown=None)
        self._create_embedding_state(
            paper_id,
            embedding_provider="sentence_transformers",
            embedding_model="all-MiniLM-L6-v2",
            status=EMBEDDING_STATUS_READY,
            collection_name="paper_sections__sentence_transformers__minilm__legacy",
        )

        with patch(
            "app.services.paper_embeddings.embed_and_store_sections",
            return_value=3,
        ) as mock_embed, patch(
            "app.services.paper_embeddings.delete_by_paper_from_active_collection"
        ) as mock_delete:
            response = self.client.post(f"/papers/{paper_id}/reembed")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["paper_id"], paper_id)
        self.assertEqual(payload["num_chunks_embedded"], 3)
        self.assertEqual(payload["embedding_status"], "ready")
        mock_delete.assert_called_once_with(paper_id)
        mock_embed.assert_called_once()

        with self.session_local() as db:
            active_state = (
                db.query(PaperEmbeddingState)
                .filter(
                    PaperEmbeddingState.paper_id == uuid.UUID(paper_id),
                    PaperEmbeddingState.embedding_provider == "openai",
                    PaperEmbeddingState.embedding_model == "text-embedding-3-small",
                )
                .first()
            )
            self.assertIsNotNone(active_state)
            self.assertEqual(active_state.status, EMBEDDING_STATUS_READY)
            self.assertEqual(active_state.chunk_count, 3)

    def test_bulk_reembed_defaults_to_non_ready_papers_only(self):
        ready_paper_id = self._create_paper("Ready Paper", breakdown=None)
        stale_paper_id = self._create_paper("Stale Paper", breakdown=None)
        self._create_embedding_state(
            ready_paper_id,
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            status=EMBEDDING_STATUS_READY,
        )
        self._create_embedding_state(
            stale_paper_id,
            embedding_provider="sentence_transformers",
            embedding_model="all-MiniLM-L6-v2",
            status=EMBEDDING_STATUS_READY,
            collection_name="paper_sections__sentence_transformers__minilm__legacy",
        )

        with patch(
            "app.services.paper_embeddings.embed_and_store_sections",
            return_value=2,
        ), patch("app.services.paper_embeddings.delete_by_paper_from_active_collection"):
            response = self.client.post("/papers/reembed", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["requested_count"], 2)
        self.assertEqual(payload["reembedded_count"], 1)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["results"][0]["paper_id"], stale_paper_id)

    def test_reembed_endpoints_validate_ids_and_missing_papers(self):
        bad_id_response = self.client.post("/papers/not-a-uuid/reembed")
        self.assertEqual(bad_id_response.status_code, 400)

        missing_id_response = self.client.post(
            "/papers/reembed",
            json={"paper_ids": [str(uuid.uuid4())]},
        )
        self.assertEqual(missing_id_response.status_code, 404)

    def test_reembed_maps_provider_configuration_failures_to_503(self):
        paper_id = self._create_paper("Broken Provider Paper", breakdown=None)

        with patch(
            "app.services.paper_embeddings.embed_and_store_sections",
            side_effect=MissingProviderCredentialsError("missing key"),
        ), patch("app.services.paper_embeddings.delete_by_paper_from_active_collection"):
            response = self.client.post(f"/papers/{paper_id}/reembed")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], CONFIGURATION_ERROR_DETAIL)

        with self.session_local() as db:
            active_state = (
                db.query(PaperEmbeddingState)
                .filter(PaperEmbeddingState.paper_id == uuid.UUID(paper_id))
                .first()
            )
            self.assertIsNotNone(active_state)
            self.assertEqual(active_state.status, EMBEDDING_STATUS_FAILED)

    def test_pdf_upload_rejects_non_pdf_files(self):
        response = self.client.post(
            "/papers/ingest/pdf",
            files={"file": ("notes.txt", b"not a pdf", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "File must be a PDF")

    def test_pdf_upload_maps_corrupt_pdf_to_user_safe_422(self):
        response = self.client.post(
            "/papers/ingest/pdf",
            files={"file": ("broken.pdf", b"not a real pdf", "application/pdf")},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], PDF_READ_ERROR_DETAIL)

        with self.session_local() as db:
            self.assertEqual(db.query(Paper).count(), 0)

    def test_arxiv_ingest_maps_timeout_to_user_safe_503(self):
        with patch(
            "app.routers.papers.fetch_arxiv_metadata",
            side_effect=UserSafeServiceError(503, ARXIV_UNAVAILABLE_DETAIL),
        ):
            response = self.client.post(
                "/papers/ingest/arxiv",
                json={"arxiv_url": "2401.12345"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], ARXIV_UNAVAILABLE_DETAIL)

    def test_arxiv_ingest_maps_missing_paper_to_user_safe_404(self):
        with patch(
            "app.routers.papers.fetch_arxiv_metadata",
            side_effect=UserSafeServiceError(404, ARXIV_NOT_FOUND_DETAIL),
        ):
            response = self.client.post(
                "/papers/ingest/arxiv",
                json={"arxiv_url": "2401.12345"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], ARXIV_NOT_FOUND_DETAIL)

    def test_arxiv_ingest_maps_pdf_parse_failure_to_user_safe_422(self):
        with patch(
            "app.routers.papers.fetch_arxiv_metadata",
            return_value={
                "title": "Paper",
                "authors": "Author",
                "abstract": "Abstract",
            },
        ), patch(
            "app.routers.papers.download_arxiv_pdf",
            return_value=Path("/tmp/papertrail-test.pdf"),
        ), patch(
            "app.routers.papers.extract_text",
            side_effect=UserSafeServiceError(422, PDF_READ_ERROR_DETAIL),
        ):
            response = self.client.post(
                "/papers/ingest/arxiv",
                json={"arxiv_url": "2401.12345"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], PDF_READ_ERROR_DETAIL)

        with self.session_local() as db:
            self.assertEqual(db.query(Paper).count(), 0)

    def test_pdf_ingest_still_saves_paper_when_embedding_fails(self):
        sections = [
            {
                "title": "Abstract",
                "order": 0,
                "content": "This paper studies deterministic tests.",
            }
        ]

        with patch(
            "app.routers.papers.extract_text",
            return_value="Abstract\nThis paper studies deterministic tests.",
        ), patch(
            "app.routers.papers.extract_metadata",
            return_value={"title": "Embedding Failure Paper", "authors": "A. Tester"},
        ), patch(
            "app.routers.papers.split_into_sections",
            return_value=sections,
        ), patch(
            "app.routers.papers.sync_paper_embeddings",
            side_effect=RuntimeError("embedding backend unavailable"),
        ):
            response = self.client.post(
                "/papers/ingest/pdf",
                files={"file": ("paper.pdf", b"fake", "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "Embedding Failure Paper")
        self.assertEqual(payload["num_sections"], 1)
        self.assertEqual(payload["num_chunks_embedded"], 0)

        with self.session_local() as db:
            self.assertEqual(db.query(Paper).count(), 1)
            self.assertEqual(db.query(PaperSection).count(), 1)

    def test_fetch_arxiv_metadata_maps_empty_atom_feed_to_404(self):
        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return None

            async def get(self, url):
                return httpx.Response(
                    200,
                    text="<feed><title>arXiv Query Results</title></feed>",
                    request=httpx.Request("GET", url),
                )

        with patch("app.services.arxiv_fetcher.httpx.AsyncClient", FakeClient):
            with self.assertRaises(UserSafeServiceError) as context:
                asyncio.run(fetch_arxiv_metadata("2401.12345"))

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, ARXIV_NOT_FOUND_DETAIL)

    def test_download_arxiv_pdf_rejects_invalid_pdf_without_writing_file(self):
        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return None

            async def get(self, url):
                return httpx.Response(
                    200,
                    content=b"<html>not a pdf</html>",
                    request=httpx.Request("GET", url),
                )

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_dir = Path(tmpdir)
            with patch("app.services.arxiv_fetcher.PDF_DIR", pdf_dir), patch(
                "app.services.arxiv_fetcher.httpx.AsyncClient",
                FakeClient,
            ):
                with self.assertRaises(UserSafeServiceError) as context:
                    asyncio.run(download_arxiv_pdf("2401.12345"))

            self.assertEqual(context.exception.status_code, 502)
            self.assertEqual(context.exception.detail, ARXIV_INVALID_PDF_DETAIL)
            self.assertFalse((pdf_dir / "2401.12345.pdf").exists())


if __name__ == "__main__":
    unittest.main()
