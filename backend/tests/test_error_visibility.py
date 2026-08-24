import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import UNEXPECTED_ERROR_DETAIL, app
from app.services.discovery import (
    STAGE_GENERATING_QUERIES,
    STAGE_RANKING_RESULTS,
    STAGE_SEARCHING_ARXIV,
    run_discovery,
)

ORIGIN = "http://localhost:3000"


class UnhandledErrorTests(unittest.TestCase):
    """An unhandled error must reach the browser as a readable 500.

    Starlette re-raises unhandled exceptions, which skips CORSMiddleware and
    strips the Access-Control-Allow-Origin header. The browser then reports a
    CORS violation, hiding the real error - exactly what made the original
    default-user race so hard to diagnose.
    """

    def setUp(self):
        self.init_db_patch = patch("app.main.init_db", return_value=None)
        self.init_db_patch.start()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()
        self.init_db_patch.stop()

    def _crash(self):
        return patch(
            "app.main.build_health_details",
            side_effect=RuntimeError("boom"),
        )

    def test_unhandled_error_returns_500_not_a_raised_exception(self):
        with self._crash():
            response = self.client.get("/health/details")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], UNEXPECTED_ERROR_DETAIL)

    def test_unhandled_error_keeps_cors_headers(self):
        with self._crash():
            response = self.client.get(
                "/health/details", headers={"Origin": ORIGIN}
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"), ORIGIN
        )

    def test_error_response_does_not_leak_internals(self):
        with self._crash():
            response = self.client.get("/health/details")

        self.assertNotIn("boom", response.text)
        self.assertNotIn("Traceback", response.text)

    def test_successful_requests_are_unaffected(self):
        response = self.client.get("/health", headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"), ORIGIN
        )


class DiscoveryStageReportingTests(unittest.IsolatedAsyncioTestCase):
    """A failed run must show which stage it reached."""

    async def test_reports_each_stage_in_order(self):
        stages = []
        with patch(
            "app.services.discovery.generate_search_queries",
            return_value=["q1"],
        ), patch(
            "app.services.discovery.search_arxiv_multi", return_value=[]
        ), patch(
            "app.services.discovery.rank_results", return_value=[]
        ):
            await run_discovery("question", on_stage=stages.append)

        self.assertEqual(
            stages,
            [
                STAGE_GENERATING_QUERIES,
                STAGE_SEARCHING_ARXIV,
                STAGE_RANKING_RESULTS,
            ],
        )

    async def test_queries_are_reported_before_the_arxiv_stage(self):
        """The queries must survive a later arXiv failure."""
        seen = {}
        stages = []

        with patch(
            "app.services.discovery.generate_search_queries",
            return_value=["q1", "q2"],
        ), patch(
            "app.services.discovery.search_arxiv_multi",
            side_effect=RuntimeError("arxiv down"),
        ):
            with self.assertRaises(RuntimeError):
                await run_discovery(
                    "question",
                    on_stage=stages.append,
                    on_queries=lambda q: seen.setdefault("queries", q),
                )

        self.assertEqual(seen["queries"], ["q1", "q2"])
        self.assertEqual(stages[-1], STAGE_SEARCHING_ARXIV)

    async def test_stage_stays_at_generation_when_the_model_fails(self):
        stages = []
        with patch(
            "app.services.discovery.generate_search_queries",
            side_effect=RuntimeError("model down"),
        ):
            with self.assertRaises(RuntimeError):
                await run_discovery("question", on_stage=stages.append)

        self.assertEqual(stages, [STAGE_GENERATING_QUERIES])

    async def test_callbacks_are_optional(self):
        with patch(
            "app.services.discovery.generate_search_queries",
            return_value=["q1"],
        ), patch(
            "app.services.discovery.search_arxiv_multi", return_value=[]
        ), patch(
            "app.services.discovery.rank_results", return_value=[]
        ):
            result = await run_discovery("question")

        self.assertEqual(result["queries"], ["q1"])



class DiscoveryFailureRecordingTests(unittest.TestCase):
    """A failed background run must record its progress in the database."""

    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.database import Base

        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_local = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self):
        Base_metadata = __import__(
            "app.database", fromlist=["Base"]
        ).Base.metadata
        Base_metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _run_discovery_task(self, task_session_local=None, **discovery_patches):
        import asyncio

        from app.models.models import DiscoveryRun, User
        from app.routers.discovery import _execute_discovery

        with self.session_local() as db:
            user = User(email="local@papertrail.dev", name="Local User")
            db.add(user)
            db.commit()
            run = DiscoveryRun(user_id=user.id, question="q", status="pending")
            db.add(run)
            db.commit()
            run_id = run.id

        with patch(
            "app.database.SessionLocal",
            task_session_local or self.session_local,
        ), patch.multiple(
            "app.services.discovery", **discovery_patches
        ):
            asyncio.run(_execute_discovery(run_id, "q", 5))

        with self.session_local() as db:
            return db.query(DiscoveryRun).filter(DiscoveryRun.id == run_id).one()

    def test_arxiv_failure_keeps_the_queries_and_names_the_stage(self):
        from unittest.mock import AsyncMock

        run = self._run_discovery_task(
            generate_search_queries=AsyncMock(return_value=["q1", "q2"]),
            search_arxiv_multi=AsyncMock(side_effect=RuntimeError("arxiv down")),
        )

        self.assertEqual(run.status, "failed")
        # The evidence that used to be lost.
        self.assertEqual(run.generated_queries, ["q1", "q2"])
        self.assertEqual(
            (run.budget_used or {}).get("failed_stage"), STAGE_SEARCHING_ARXIV
        )

    def test_model_failure_is_attributed_to_query_generation(self):
        from unittest.mock import AsyncMock

        run = self._run_discovery_task(
            generate_search_queries=AsyncMock(side_effect=RuntimeError("model down")),
        )

        self.assertEqual(run.status, "failed")
        self.assertIsNone(run.generated_queries)
        self.assertEqual(
            (run.budget_used or {}).get("failed_stage"), STAGE_GENERATING_QUERIES
        )

    def test_a_mid_run_commit_failure_still_marks_the_run_failed(self):
        """The failure handler must survive the database itself failing.

        SQLAlchemy leaves a session unusable after a failed commit until it is
        rolled back; every later commit raises PendingRollbackError. Without a
        rollback in the handler, a commit failure inside the run leaves the row
        stuck in "running" forever.
        """
        from unittest.mock import AsyncMock

        from sqlalchemy.exc import OperationalError, PendingRollbackError
        from sqlalchemy.orm import Session as SASession, sessionmaker

        class _BrokenAfterFailedCommitSession(SASession):
            commit_calls = 0
            fail_on_call = 2  # 1: status="running", 2: persisting the queries
            needs_rollback = False

            def commit(self):
                cls = _BrokenAfterFailedCommitSession
                if cls.needs_rollback:
                    raise PendingRollbackError(
                        "This Session's transaction has been rolled back"
                    )
                cls.commit_calls += 1
                if cls.commit_calls == cls.fail_on_call:
                    cls.needs_rollback = True
                    raise OperationalError("UPDATE", {}, Exception("disk I/O error"))
                return super().commit()

            def rollback(self):
                _BrokenAfterFailedCommitSession.needs_rollback = False
                return super().rollback()

        broken_session_local = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            class_=_BrokenAfterFailedCommitSession,
        )

        run = self._run_discovery_task(
            task_session_local=broken_session_local,
            generate_search_queries=AsyncMock(return_value=["q1", "q2"]),
        )

        self.assertEqual(run.status, "failed")
        self.assertEqual(
            (run.budget_used or {}).get("failed_stage"), STAGE_GENERATING_QUERIES
        )

if __name__ == "__main__":
    unittest.main()
