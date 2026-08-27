import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.models import Paper, User
from scripts.backfill_arxiv_url import backfill_arxiv_urls


class BackfillArxivUrlTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_local = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed(self, arxiv_url: str | None) -> uuid.UUID:
        with self.session_local() as db:
            user = (
                db.query(User).filter(User.email == "local@papertrail.dev").first()
            )
            if not user:
                user = User(email="local@papertrail.dev", name="Local User")
                db.add(user)
                db.flush()
            paper = Paper(
                user_id=user.id,
                title="P",
                authors="",
                abstract="",
                raw_text="",
                arxiv_url=arxiv_url,
            )
            db.add(paper)
            db.commit()
            return paper.id

    def test_rewrites_non_canonical_forms(self):
        for stored in (
            "2401.12345",
            "arxiv.org/abs/2401.12345",
            "https://arxiv.org/pdf/2401.12345v2",
        ):
            with self.subTest(stored=stored):
                paper_id = self._seed(stored)

                with self.session_local() as db:
                    result = backfill_arxiv_urls(db)

                self.assertEqual(result["rows_changed"], 1)
                with self.session_local() as db:
                    paper = db.query(Paper).filter(Paper.id == paper_id).one()
                    self.assertEqual(
                        paper.arxiv_url, "https://arxiv.org/abs/2401.12345"
                    )
                    db.delete(paper)
                    db.commit()

    def test_leaves_unrepairable_rows_alone(self):
        for stored in (
            "https://arxiv.org/abs/2401.12345",
            "https://arxiv.org/abs/Alpha_Paper",
            None,
        ):
            with self.subTest(stored=stored):
                paper_id = self._seed(stored)

                with self.session_local() as db:
                    self.assertEqual(backfill_arxiv_urls(db)["rows_changed"], 0)

                with self.session_local() as db:
                    paper = db.query(Paper).filter(Paper.id == paper_id).one()
                    self.assertEqual(paper.arxiv_url, stored)
                    db.delete(paper)
                    db.commit()

    def test_second_run_changes_nothing(self):
        self._seed("2401.12345")

        with self.session_local() as db:
            backfill_arxiv_urls(db)
        with self.session_local() as db:
            self.assertEqual(backfill_arxiv_urls(db)["rows_changed"], 0)


if __name__ == "__main__":
    unittest.main()
