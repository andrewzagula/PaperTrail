import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.models import User
from app.services.users import DEFAULT_USER_EMAIL, get_or_create_default_user


class DefaultUserTests(unittest.TestCase):
    """Regression coverage for the lazy default-user creation race.

    These use a file-backed SQLite database rather than the shared in-memory
    StaticPool the other suites use, because the race requires each session to
    hold its own connection and transaction, as it does in production.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp.name) / "papertrail_test.db"
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        self.session_local = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()
        self._tmp.cleanup()

    def _default_user_count(self) -> int:
        db = self.session_local()
        try:
            return (
                db.query(User).filter(User.email == DEFAULT_USER_EMAIL).count()
            )
        finally:
            db.close()

    def test_creates_default_user_once_and_is_idempotent(self):
        db = self.session_local()
        try:
            first = get_or_create_default_user(db)
            second = get_or_create_default_user(db)
            self.assertEqual(first.id, second.id)
            self.assertEqual(first.email, DEFAULT_USER_EMAIL)
        finally:
            db.close()

        self.assertEqual(self._default_user_count(), 1)

    def test_returns_winning_row_when_another_session_inserts_first(self):
        """The caller that loses the insert must return the winner, not raise.

        Deterministically reproduces the interleaving: a competing session
        commits the same row while this caller is mid-commit, so the commit
        fails on the users.email unique constraint.
        """
        real_commit = Session.commit
        raced = threading.Event()
        winner_id = {}

        def racing_commit(session):
            if not raced.is_set():
                raced.set()
                other = self.session_local()
                try:
                    rival = User(email=DEFAULT_USER_EMAIL, name="Local User")
                    other.add(rival)
                    other.commit()
                    winner_id["id"] = rival.id
                finally:
                    other.close()
            return real_commit(session)

        db = self.session_local()
        try:
            with patch.object(Session, "commit", racing_commit):
                user = get_or_create_default_user(db)
            self.assertEqual(user.id, winner_id["id"])
            self.assertEqual(user.email, DEFAULT_USER_EMAIL)
        finally:
            db.close()

        self.assertTrue(raced.is_set(), "the racing commit never ran")
        self.assertEqual(self._default_user_count(), 1)

    def test_concurrent_callers_converge_on_one_user(self):
        workers = 6
        barrier = threading.Barrier(workers)

        def resolve(_):
            db = self.session_local()
            try:
                barrier.wait(timeout=10)
                return str(get_or_create_default_user(db).id)
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            user_ids = list(pool.map(resolve, range(workers)))

        self.assertEqual(len(set(user_ids)), 1, f"diverging users: {user_ids}")
        self.assertEqual(self._default_user_count(), 1)


class DefaultUserEndpointRaceTests(unittest.TestCase):
    """The frontend loads /papers/ and /discover/ in parallel on first paint.

    Against a fresh database both requests resolve the default user at once,
    which is what surfaced the original 500.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp.name) / "papertrail_test.db"
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
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
        self.engine.dispose()
        self._tmp.cleanup()

    def test_parallel_first_load_does_not_error(self):
        paths = ["/papers/", "/discover/"]
        barrier = threading.Barrier(len(paths))

        def fetch(path):
            barrier.wait(timeout=10)
            return path, self.client.get(path)

        with ThreadPoolExecutor(max_workers=len(paths)) as pool:
            results = list(pool.map(fetch, paths))

        for path, response in results:
            self.assertEqual(
                response.status_code, 200, f"{path} -> {response.text}"
            )

        db = self.session_local()
        try:
            self.assertEqual(
                db.query(User).filter(User.email == DEFAULT_USER_EMAIL).count(),
                1,
            )
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
