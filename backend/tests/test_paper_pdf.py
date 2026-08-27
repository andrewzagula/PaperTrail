import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Paper, User
from app.routers.papers import PDF_NOT_AVAILABLE_DETAIL
from app.services.arxiv_fetcher import PDF_DIR

MINIMAL_PDF = b"%PDF-1.4\n%%EOF\n"


class PaperPdfEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_local = sessionmaker(bind=self.engine)

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
        self.written: list[Path] = []

    def tearDown(self):
        for path in self.written:
            path.unlink(missing_ok=True)
        self.client.close()
        app.dependency_overrides.clear()
        self.init_db_patch.stop()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _paper(self, pdf_path) -> uuid.UUID:
        with self.session_local() as db:
            user = User(email="local@papertrail.dev", name="Local User")
            db.add(user)
            db.flush()
            paper = Paper(
                user_id=user.id,
                title="P",
                authors="",
                abstract="",
                raw_text="",
                pdf_path=pdf_path,
            )
            db.add(paper)
            db.commit()
            return paper.id

    def _write_pdf(self, name: str) -> Path:
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        path = PDF_DIR / name
        path.write_bytes(MINIMAL_PDF)
        self.written.append(path)
        return path

    def test_serves_a_pdf_stored_under_the_pdf_directory(self):
        path = self._write_pdf("test-" + str(uuid.uuid4()) + ".pdf")
        paper_id = self._paper(str(path))

        response = self.client.get("/papers/" + str(paper_id) + "/pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.content, MINIMAL_PDF)

    def test_404s_when_the_paper_has_no_pdf_path(self):
        paper_id = self._paper(None)

        response = self.client.get("/papers/" + str(paper_id) + "/pdf")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], PDF_NOT_AVAILABLE_DETAIL)

    def test_404s_when_the_file_is_gone_from_disk(self):
        paper_id = self._paper(str(PDF_DIR / "definitely-not-here.pdf"))

        response = self.client.get("/papers/" + str(paper_id) + "/pdf")

        self.assertEqual(response.status_code, 404)

    def test_refuses_a_path_outside_the_pdf_directory(self):
        """A tampered row must not turn this endpoint into arbitrary file read."""
        paper_id = self._paper(str(PDF_DIR.parent / "papertrail.db"))

        response = self.client.get("/papers/" + str(paper_id) + "/pdf")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], PDF_NOT_AVAILABLE_DETAIL)


if __name__ == "__main__":
    unittest.main()
