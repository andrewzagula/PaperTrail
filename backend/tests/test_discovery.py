import asyncio
import uuid
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.llm.errors import CONFIGURATION_ERROR_DETAIL, MissingProviderCredentialsError
from app.main import app
from app.models.models import DiscoveryResult, DiscoveryRun, User
from app.routers.discovery import DiscoverRequest, _execute_discovery
from app.services.arxiv_fetcher import ARXIV_NOT_FOUND_DETAIL
from app.services.arxiv_searcher import ArxivResult
from app.services.discovery import (
    FEWER_QUERIES_WARNING,
    LOW_UNIQUE_RESULTS_WARNING,
    NO_HIGH_CONFIDENCE_RESULTS_WARNING,
    NO_UNIQUE_RESULTS_WARNING,
    SMALL_RESULT_BUDGET_WARNING,
    generate_search_queries,
    run_discovery,
)
from app.services.errors import UserSafeServiceError
from app.services.pdf_parser import PDF_READ_ERROR_DETAIL

DEFAULT_USER_EMAIL = "local@papertrail.dev"


def _arxiv_result(arxiv_id: str) -> ArxivResult:
    return ArxivResult(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        authors="A. Author",
        abstract="Abstract",
        published="2024-01-01",
    )


class DiscoveryGuardrailServiceTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.discovery.get_structured_client")
    async def test_generate_search_queries_drops_blank_and_duplicate_queries(
        self,
        mock_get_structured_client,
    ):
        client = Mock()
        client.generate_structured.return_value = {
            "queries": [
                " transformer pruning ",
                "",
                "Transformer Pruning",
                "model sparsity",
                "model sparsity ",
            ],
        }
        mock_get_structured_client.return_value = client

        queries = await generate_search_queries(
            "How do I prune transformer models?",
            max_queries=5,
        )

        self.assertEqual(queries, ["transformer pruning", "model sparsity"])

    @patch("app.services.discovery.rank_results", new_callable=AsyncMock)
    @patch("app.services.discovery.search_arxiv_multi", new_callable=AsyncMock)
    @patch("app.services.discovery.generate_search_queries", new_callable=AsyncMock)
    async def test_run_discovery_warns_for_too_few_queries_zero_results_and_small_budget(
        self,
        mock_generate_search_queries,
        mock_search_arxiv_multi,
        mock_rank_results,
    ):
        mock_generate_search_queries.return_value = ["query one"]
        mock_search_arxiv_multi.return_value = []
        mock_rank_results.return_value = []

        result = await run_discovery(
            "efficient transformer inference",
            max_queries=3,
            max_return=3,
        )

        self.assertIn(FEWER_QUERIES_WARNING, result["warnings"])
        self.assertIn(NO_UNIQUE_RESULTS_WARNING, result["warnings"])
        self.assertIn(SMALL_RESULT_BUDGET_WARNING, result["warnings"])
        self.assertEqual(result["budget_used"]["warnings"], result["warnings"])
        self.assertEqual(result["budget_used"]["max_results_requested"], 3)

    @patch("app.services.discovery.rank_results", new_callable=AsyncMock)
    @patch("app.services.discovery.search_arxiv_multi", new_callable=AsyncMock)
    @patch("app.services.discovery.generate_search_queries", new_callable=AsyncMock)
    async def test_run_discovery_warns_for_few_results_and_low_confidence_scores(
        self,
        mock_generate_search_queries,
        mock_search_arxiv_multi,
        mock_rank_results,
    ):
        mock_generate_search_queries.return_value = ["query one", "query two", "query three"]
        mock_search_arxiv_multi.return_value = [
            _arxiv_result("2401.00001"),
            _arxiv_result("2401.00002"),
            _arxiv_result("2401.00003"),
        ]
        mock_rank_results.return_value = [
            {
                "arxiv_id": "2401.00001",
                "title": "Paper 2401.00001",
                "authors": "A. Author",
                "abstract": "Abstract",
                "published": "2024-01-01",
                "relevance_score": 0.59,
                "relevance_reason": "Weak match.",
            }
        ]

        result = await run_discovery(
            "efficient transformer inference",
            max_queries=3,
            max_return=10,
        )

        self.assertIn(LOW_UNIQUE_RESULTS_WARNING, result["warnings"])
        self.assertIn(NO_HIGH_CONFIDENCE_RESULTS_WARNING, result["warnings"])
        self.assertNotIn(NO_UNIQUE_RESULTS_WARNING, result["warnings"])
        self.assertNotIn(SMALL_RESULT_BUDGET_WARNING, result["warnings"])


class DiscoveryEndpointTests(unittest.TestCase):
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

    def _create_discovery_result(self) -> tuple[str, str]:
        with self.session_local() as db:
            run = DiscoveryRun(
                user_id=self._get_or_create_user(),
                question="efficient transformer inference",
                status="complete",
            )
            db.add(run)
            db.flush()
            result = DiscoveryResult(
                run_id=run.id,
                arxiv_id="2401.12345",
                title="Discovery Result Paper",
                authors="A. Author",
                abstract="Abstract",
                published="2024-01-01",
                relevance_score=0.9,
                relevance_reason="Relevant",
                rank_order=1,
            )
            db.add(result)
            db.commit()
            return str(run.id), str(result.id)

    def test_discovery_rejects_result_budget_above_phase_cap(self):
        with self.assertRaises(ValidationError):
            DiscoverRequest(
                question="efficient transformer inference",
                max_results=21,
            )

    def test_discovery_result_ingest_maps_arxiv_failure_to_user_safe_error(self):
        run_id, result_id = self._create_discovery_result()

        with patch(
            "app.routers.discovery.fetch_arxiv_metadata",
            side_effect=UserSafeServiceError(404, ARXIV_NOT_FOUND_DETAIL),
        ):
            response = self.client.post(f"/discover/{run_id}/ingest/{result_id}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], ARXIV_NOT_FOUND_DETAIL)

    def test_discovery_result_ingest_maps_pdf_failure_to_user_safe_error(self):
        run_id, result_id = self._create_discovery_result()

        with patch(
            "app.routers.discovery.fetch_arxiv_metadata",
            return_value={
                "title": "Discovery Result Paper",
                "authors": "A. Author",
                "abstract": "Abstract",
            },
        ), patch(
            "app.routers.discovery.download_arxiv_pdf",
            return_value=Path("/tmp/papertrail-discovery-test.pdf"),
        ), patch(
            "app.routers.discovery.extract_text",
            side_effect=UserSafeServiceError(422, PDF_READ_ERROR_DETAIL),
        ):
            response = self.client.post(f"/discover/{run_id}/ingest/{result_id}")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], PDF_READ_ERROR_DETAIL)

    def test_discovery_background_provider_errors_remain_sanitized(self):
        with self.session_local() as db:
            run = DiscoveryRun(
                user_id=self._get_or_create_user(),
                question="efficient transformer inference",
                status="pending",
            )
            db.add(run)
            db.commit()
            run_id = uuid.UUID(str(run.id))

        with patch("app.database.SessionLocal", self.session_local), patch(
            "app.services.discovery.run_discovery",
            side_effect=MissingProviderCredentialsError("raw missing credential"),
        ):
            asyncio.run(_execute_discovery(run_id, "efficient transformer inference", 10))

        with self.session_local() as db:
            updated_run = db.query(DiscoveryRun).filter(DiscoveryRun.id == run_id).one()
            self.assertEqual(updated_run.status, "failed")
            self.assertEqual(updated_run.error_message, CONFIGURATION_ERROR_DETAIL)

    def test_discovery_background_persists_and_returns_quality_warnings(self):
        with self.session_local() as db:
            run = DiscoveryRun(
                user_id=self._get_or_create_user(),
                question="efficient transformer inference",
                status="pending",
            )
            db.add(run)
            db.commit()
            run_id = uuid.UUID(str(run.id))

        discovery_warning = NO_HIGH_CONFIDENCE_RESULTS_WARNING
        discovery_payload = {
            "queries": ["query one"],
            "ranked_results": [
                {
                    "arxiv_id": "2401.12345",
                    "title": "Discovery Result Paper",
                    "authors": "A. Author",
                    "abstract": "Abstract",
                    "published": "2024-01-01",
                    "relevance_score": 0.55,
                    "relevance_reason": "Weak but related.",
                }
            ],
            "budget_used": {
                "queries_generated": 1,
                "total_papers_fetched": 1,
                "papers_ranked": 1,
            },
            "warnings": [discovery_warning],
        }

        with patch("app.database.SessionLocal", self.session_local), patch(
            "app.services.discovery.run_discovery",
            new_callable=AsyncMock,
        ) as mock_run_discovery:
            mock_run_discovery.return_value = discovery_payload
            asyncio.run(_execute_discovery(run_id, "efficient transformer inference", 10))

        response = self.client.get(f"/discover/{run_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["warnings"], [discovery_warning])
        self.assertEqual(payload["budget_used"]["warnings"], [discovery_warning])
        self.assertEqual(payload["budget_used"]["max_results_requested"], 10)
        self.assertEqual(payload["results"][0]["title"], "Discovery Result Paper")


if __name__ == "__main__":
    unittest.main()
