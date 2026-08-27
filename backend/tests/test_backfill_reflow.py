import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.models import Paper, PaperSection, User
from scripts.backfill_reflow import backfill_sections


class BackfillReflowTests(unittest.TestCase):
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

    def _seed(self, content: str) -> uuid.UUID:
        with self.session_local() as db:
            user = User(email="local@papertrail.dev", name="Local User")
            db.add(user)
            db.flush()
            paper = Paper(
                user_id=user.id, title="P", authors="", abstract="", raw_text=""
            )
            db.add(paper)
            db.flush()
            db.add(
                PaperSection(
                    paper_id=paper.id,
                    section_title="Introduction",
                    content=content,
                    section_order=0,
                )
            )
            db.commit()
            return paper.id

    def test_rewrites_damaged_content(self):
        paper_id = self._seed("achieved re-\nmarkable success")

        with self.session_local() as db:
            result = backfill_sections(db)

        self.assertEqual(result["rows_changed"], 1)
        self.assertEqual(result["paper_ids"], [str(paper_id)])

        with self.session_local() as db:
            self.assertEqual(
                db.query(PaperSection).one().content, "achieved remarkable success"
            )

    def test_second_run_changes_nothing(self):
        self._seed("achieved re-\nmarkable success")

        with self.session_local() as db:
            backfill_sections(db)
        with self.session_local() as db:
            self.assertEqual(backfill_sections(db)["rows_changed"], 0)

    def test_leaves_clean_content_alone(self):
        self._seed("already clean prose")

        with self.session_local() as db:
            self.assertEqual(backfill_sections(db)["rows_changed"], 0)


if __name__ == "__main__":
    unittest.main()
