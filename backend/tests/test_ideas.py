import uuid
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.llm.errors import ProviderRequestError, REQUEST_ERROR_DETAIL
from app.main import app
from app.models.models import Paper, PaperSection, SavedItem, User
from app.services.paper_ideas import (
    CANDIDATE_GENERATION_FALLBACK_WARNING,
    CRITIQUE_FALLBACK_WARNING,
    critique_and_filter_ideas,
    generate_candidate_ideas,
)

DEFAULT_USER_EMAIL = "local@papertrail.dev"


def make_breakdown(label: str) -> dict:
    return {
        "problem": f"{label} problem",
        "method": f"{label} method",
        "key_contributions": f"{label} contributions",
        "results": f"{label} results",
        "limitations": f"{label} limitations",
        "future_work": f"{label} future work",
    }


def make_idea(
    index: int,
    transformation_type: str = "extend",
    prefix: str = "Idea",
) -> dict:
    return {
        "title": f"{prefix} {index}",
        "transformation_type": transformation_type,
        "description": f"{prefix} {index} description",
        "why_interesting": f"{prefix} {index} is interesting",
        "feasibility": "medium",
        "evidence_basis": [f"{prefix} {index} evidence"],
        "risks_or_unknowns": [f"{prefix} {index} risk"],
        "warnings": [],
    }


def make_candidate_payload() -> dict:
    transformations = ["combine", "ablate", "extend", "apply", "extend", "ablate"]
    return {
        "candidates": [
            make_idea(index + 1, transformation, prefix="Candidate")
            for index, transformation in enumerate(transformations)
        ],
        "warnings": [],
    }


def make_critique_payload() -> dict:
    return {
        "ideas": [
            make_idea(1, "combine", prefix="Final"),
            make_idea(2, "ablate", prefix="Final"),
            make_idea(3, "extend", prefix="Final"),
        ],
        "warnings": [],
    }


class IdeasEndpointTests(unittest.TestCase):
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
        self.generate_patch = patch(
            "app.services.paper_ideas.generate_candidate_ideas",
            return_value=make_candidate_payload(),
        )
        self.mock_generate_candidates = self.generate_patch.start()
        self.critique_patch = patch(
            "app.services.paper_ideas.critique_and_filter_ideas",
            return_value=make_critique_payload(),
        )
        self.mock_critique = self.critique_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.critique_patch.stop()
        self.generate_patch.stop()
        self.init_db_patch.stop()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _get_or_create_user(self, email: str = DEFAULT_USER_EMAIL) -> str:
        with self.session_local() as db:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(email=email, name="Local User")
                db.add(user)
                db.commit()
                db.refresh(user)
            return str(user.id)

    def _create_paper(
        self,
        title: str,
        breakdown: dict | None = None,
        with_breakdown: bool = True,
        user_email: str = DEFAULT_USER_EMAIL,
    ) -> str:
        user_id = self._get_or_create_user(user_email)
        structured_breakdown = breakdown
        if structured_breakdown is None and with_breakdown:
            structured_breakdown = make_breakdown(title)

        with self.session_local() as db:
            paper = Paper(
                user_id=uuid.UUID(user_id),
                title=title,
                authors=f"{title} Authors",
                abstract=f"{title} abstract",
                arxiv_url=f"https://arxiv.org/abs/{title.replace(' ', '_')}",
                pdf_path=f"/tmp/{title.replace(' ', '_')}.pdf",
                raw_text=f"{title} raw text",
                structured_breakdown=structured_breakdown,
            )
            db.add(paper)
            db.flush()

            sections = [
                ("Abstract", f"{title} abstract section"),
                ("Method", f"{title} method section"),
                ("Experiments", f"{title} experiments section"),
                ("Limitations", f"{title} limitations section"),
            ]
            for order, (section_title, content) in enumerate(sections):
                db.add(
                    PaperSection(
                        paper_id=paper.id,
                        section_title=section_title,
                        section_order=order,
                        content=content,
                    )
                )

            db.commit()
            db.refresh(paper)
            return str(paper.id)

    def _fetch_paper_breakdown(self, paper_id: str) -> dict | None:
        with self.session_local() as db:
            paper = db.query(Paper).filter(Paper.id == uuid.UUID(paper_id)).first()
            return paper.structured_breakdown if paper else None

    def _fetch_saved_item(self, saved_item_id: str) -> dict | None:
        with self.session_local() as db:
            saved_item = (
                db.query(SavedItem)
                .filter(SavedItem.id == uuid.UUID(saved_item_id))
                .first()
            )
            if not saved_item:
                return None

            return {
                "id": str(saved_item.id),
                "title": saved_item.title,
                "item_type": saved_item.item_type,
                "paper_ids": saved_item.paper_ids,
                "data": saved_item.data,
            }

    def _make_idea_result(
        self,
        selected_papers: list[dict] | None = None,
        source_topic: str | None = "retrieval",
    ) -> dict:
        return {
            "selected_papers": selected_papers or [],
            "source_topic": source_topic,
            "ideas": [make_idea(1, "extend", prefix="Saved")],
            "warnings": [],
        }

    def _make_selected_paper(self, paper_id: str, title: str = "Paper One") -> dict:
        return {
            "id": paper_id,
            "title": title,
            "authors": f"{title} Authors",
            "arxiv_url": f"https://arxiv.org/abs/{title.replace(' ', '_')}",
            "created_at": "2026-04-27T00:00:00",
        }

    def test_generate_ideas_accepts_topic_only_request(self):
        response = self.client.post(
            "/papers/ideas",
            json={"topic": "long-context retrieval"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_papers"], [])
        self.assertEqual(payload["source_topic"], "long-context retrieval")
        self.assertEqual(len(payload["ideas"]), 3)
        self.assertEqual(payload["ideas"][0]["title"], "Final 1")
        self.assertEqual(payload["warnings"], [])

    def test_generate_ideas_accepts_one_paper_request(self):
        paper_id = self._create_paper("Paper One")

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_topic"], None)
        self.assertEqual(len(payload["ideas"]), 3)
        self.assertEqual(len(payload["selected_papers"]), 1)
        self.assertEqual(payload["selected_papers"][0]["id"], paper_id)
        self.assertEqual(payload["selected_papers"][0]["title"], "Paper One")

    def test_generate_ideas_accepts_paper_plus_topic_request(self):
        paper_id = self._create_paper("Paper One")

        response = self.client.post(
            "/papers/ideas",
            json={
                "paper_ids": [paper_id],
                "topic": "apply to small language models",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_topic"], "apply to small language models")
        self.assertEqual(payload["selected_papers"][0]["id"], paper_id)
        self.assertEqual(len(payload["ideas"]), 3)

    def test_generate_ideas_treats_blank_topic_with_papers_as_paper_only(self):
        paper_id = self._create_paper("Paper One")

        response = self.client.post(
            "/papers/ideas",
            json={
                "paper_ids": [paper_id],
                "topic": "   ",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_topic"], None)
        self.assertEqual(payload["selected_papers"][0]["id"], paper_id)
        self.assertEqual(len(payload["ideas"]), 3)

    def test_generate_ideas_rejects_empty_request(self):
        response = self.client.post("/papers/ideas", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Provide at least one paper or topic to generate ideas.",
        )

    def test_generate_ideas_rejects_blank_topic_without_papers(self):
        response = self.client.post("/papers/ideas", json={"topic": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Provide at least one paper or topic to generate ideas.",
        )

    def test_generate_ideas_rejects_too_many_papers(self):
        paper_ids = [str(uuid.uuid4()) for _ in range(6)]

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": paper_ids},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "You can use up to 5 papers for idea generation.",
        )

    def test_generate_ideas_rejects_duplicate_papers(self):
        paper_id = str(uuid.uuid4())

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id, paper_id]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Duplicate paper IDs are not allowed.")

    def test_generate_ideas_rejects_invalid_uuid(self):
        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": ["not-a-uuid"]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid paper ID: not-a-uuid")

    def test_generate_ideas_rejects_missing_paper(self):
        missing_id = str(uuid.uuid4())

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [missing_id]},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn(missing_id, response.json()["detail"])

    @patch("app.services.paper_ideas.analyze_paper", return_value=make_breakdown("generated"))
    def test_generate_ideas_creates_missing_breakdown_on_demand(self, mock_analyze):
        paper_id = self._create_paper("Paper One", with_breakdown=False)

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._fetch_paper_breakdown(paper_id)["problem"],
            "generated problem",
        )
        mock_analyze.assert_called_once()

    def test_generate_ideas_uses_candidate_fallback_for_paper_context(self):
        paper_id = self._create_paper("Paper One")
        self.mock_generate_candidates.side_effect = RuntimeError("boom")

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["ideas"]), 3)
        self.assertIn(CANDIDATE_GENERATION_FALLBACK_WARNING, payload["warnings"])

    def test_generate_ideas_uses_candidate_fallback_when_model_returns_too_few_candidates(self):
        paper_id = self._create_paper("Paper One")
        self.mock_generate_candidates.return_value = {
            "candidates": [make_idea(1, "extend", prefix="Weak Candidate")],
            "warnings": ["weak model payload"],
        }

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["ideas"]), 3)
        self.assertIn(CANDIDATE_GENERATION_FALLBACK_WARNING, payload["warnings"])
        self.mock_critique.assert_called_once()

    def test_generate_ideas_uses_critique_fallback_after_candidates_exist(self):
        paper_id = self._create_paper("Paper One")
        self.mock_critique.side_effect = RuntimeError("boom")

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["ideas"]), 5)
        self.assertEqual(payload["ideas"][0]["title"], "Candidate 1")
        self.assertIn(CRITIQUE_FALLBACK_WARNING, payload["warnings"])

    def test_generate_ideas_fills_duplicate_or_too_few_critiqued_ideas_from_candidates(self):
        paper_id = self._create_paper("Paper One")
        duplicate_idea = make_idea(1, "combine", prefix="Final")
        self.mock_critique.return_value = {
            "ideas": [duplicate_idea, duplicate_idea],
            "warnings": [],
        }

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        idea_titles = [idea["title"] for idea in payload["ideas"]]
        self.assertEqual(
            idea_titles,
            ["Final 1", "Candidate 1", "Candidate 2", "Candidate 3", "Candidate 4"],
        )

    def test_generate_ideas_normalizes_invalid_model_payload_fields(self):
        paper_id = self._create_paper("Paper One")
        bad_idea = {
            "title": "Normalized idea",
            "transformation_type": "invent",
            "description": "Use the available context.",
            "why_interesting": "It tests normalization.",
            "feasibility": "unknown",
            "evidence_basis": [],
            "risks_or_unknowns": [],
            "warnings": ["duplicate warning", "duplicate warning"],
        }
        self.mock_critique.return_value = {
            "ideas": [
                bad_idea,
                make_idea(2, "ablate", prefix="Final"),
                make_idea(3, "apply", prefix="Final"),
            ],
            "warnings": ["top-level critique warning"],
        }

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        idea = payload["ideas"][0]
        self.assertEqual(idea["title"], "Normalized idea")
        self.assertEqual(idea["transformation_type"], "extend")
        self.assertEqual(idea["feasibility"], "medium")
        self.assertEqual(idea["risks_or_unknowns"], [
            "Requires empirical validation against strong baselines."
        ])
        self.assertTrue(idea["evidence_basis"])
        self.assertIn("Paper One", idea["evidence_basis"][0])
        self.assertEqual(
            idea["warnings"],
            [
                "duplicate warning",
                "Transformation type was normalized to extend.",
                "Feasibility was normalized to medium.",
                "Evidence basis was filled from the available source context.",
            ],
        )
        self.assertIn("top-level critique warning", payload["warnings"])

    @patch("app.services.paper_ideas.analyze_paper", side_effect=RuntimeError("boom"))
    def test_generate_ideas_continues_with_warning_when_breakdown_generation_fails(
        self,
        mock_analyze,
    ):
        paper_id = self._create_paper("Paper One", with_breakdown=False)

        response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(
            any(
                warning.startswith(
                    "Paper One: Structured breakdown could not be generated automatically"
                )
                for warning in payload["warnings"]
            )
        )
        self.assertIsNone(self._fetch_paper_breakdown(paper_id))
        mock_analyze.assert_called_once()

    def test_generate_ideas_maps_provider_error_without_paper_fallback(self):
        self.mock_generate_candidates.side_effect = ProviderRequestError("bad")

        response = self.client.post(
            "/papers/ideas",
            json={"topic": "long-context retrieval"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], REQUEST_ERROR_DETAIL)
        self.mock_critique.assert_not_called()

    def test_save_ideas_persists_paper_backed_result_without_rerunning_generation(self):
        paper_id = self._create_paper("Paper One")
        generate_response = self.client.post(
            "/papers/ideas",
            json={"paper_ids": [paper_id]},
        )
        self.assertEqual(generate_response.status_code, 200)
        idea_payload = generate_response.json()
        self.assertEqual(self.mock_generate_candidates.call_count, 1)
        self.assertEqual(self.mock_critique.call_count, 1)

        with (
            patch("app.services.paper_ideas.analyze_paper") as mock_analyze,
            patch("app.services.paper_ideas.build_idea_graph") as mock_build_graph,
        ):
            save_response = self.client.post(
                "/papers/ideas/save",
                json={
                    "title": "  Long Context Retrieval Ideas  ",
                    "paper_ids": [paper_id],
                    "idea_result": idea_payload,
                },
            )

        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(self.mock_generate_candidates.call_count, 1)
        self.assertEqual(self.mock_critique.call_count, 1)
        mock_analyze.assert_not_called()
        mock_build_graph.assert_not_called()

        payload = save_response.json()
        self.assertEqual(payload["title"], "Long Context Retrieval Ideas")
        self.assertEqual(payload["item_type"], "idea")
        self.assertEqual(payload["paper_ids"], [paper_id])
        self.assertTrue(payload["created_at"])

        saved_item = self._fetch_saved_item(payload["id"])
        self.assertIsNotNone(saved_item)
        self.assertEqual(saved_item["title"], "Long Context Retrieval Ideas")
        self.assertEqual(saved_item["item_type"], "idea")
        self.assertEqual(saved_item["paper_ids"], [paper_id])
        self.assertEqual(saved_item["data"], idea_payload)

    def test_save_ideas_persists_topic_only_result_with_empty_paper_list(self):
        idea_payload = self._make_idea_result(source_topic="  long-context retrieval  ")

        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "Topic ideas",
                "idea_result": idea_payload,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["item_type"], "idea")
        self.assertEqual(payload["paper_ids"], [])

        saved_item = self._fetch_saved_item(payload["id"])
        self.assertIsNotNone(saved_item)
        self.assertEqual(saved_item["paper_ids"], [])
        self.assertEqual(saved_item["data"]["source_topic"], "long-context retrieval")

    def test_save_ideas_treats_blank_topic_with_papers_as_paper_only(self):
        paper_id = self._create_paper("Paper One")
        idea_payload = self._make_idea_result(
            selected_papers=[self._make_selected_paper(paper_id)],
            source_topic="   ",
        )

        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "Paper-only ideas",
                "paper_ids": [paper_id],
                "idea_result": idea_payload,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["paper_ids"], [paper_id])

        saved_item = self._fetch_saved_item(payload["id"])
        self.assertIsNotNone(saved_item)
        self.assertIsNone(saved_item["data"]["source_topic"])

    def test_save_ideas_rejects_blank_title(self):
        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "   ",
                "idea_result": self._make_idea_result(),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Idea title is required.")

    def test_save_ideas_rejects_title_over_limit(self):
        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "x" * 1001,
                "idea_result": self._make_idea_result(),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Idea title must be 1000 characters or fewer.",
        )

    def test_save_ideas_rejects_invalid_uuid(self):
        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "Invalid UUID ideas",
                "paper_ids": ["not-a-uuid"],
                "idea_result": self._make_idea_result(source_topic=None),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid paper ID: not-a-uuid")

    def test_save_ideas_rejects_duplicate_ids(self):
        paper_id = self._create_paper("Paper One")

        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "Duplicate ideas",
                "paper_ids": [paper_id, paper_id],
                "idea_result": self._make_idea_result(
                    selected_papers=[self._make_selected_paper(paper_id)],
                    source_topic=None,
                ),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Duplicate paper IDs are not allowed.")

    def test_save_ideas_rejects_too_many_papers(self):
        paper_ids = [str(uuid.uuid4()) for _ in range(6)]

        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "Too many ideas",
                "paper_ids": paper_ids,
                "idea_result": self._make_idea_result(source_topic=None),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "You can use up to 5 papers for idea generation.",
        )

    def test_save_ideas_rejects_missing_paper(self):
        missing_id = str(uuid.uuid4())

        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "Missing paper ideas",
                "paper_ids": [missing_id],
                "idea_result": self._make_idea_result(
                    selected_papers=[self._make_selected_paper(missing_id)],
                    source_topic=None,
                ),
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn(missing_id, response.json()["detail"])

    def test_save_ideas_rejects_selected_paper_mismatch(self):
        paper_one = self._create_paper("Paper One")
        paper_two = self._create_paper("Paper Two")
        idea_payload = self._make_idea_result(
            selected_papers=[
                self._make_selected_paper(paper_two, "Paper Two"),
                self._make_selected_paper(paper_one, "Paper One"),
            ],
            source_topic=None,
        )

        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "Mismatched ideas",
                "paper_ids": [paper_one, paper_two],
                "idea_result": idea_payload,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Idea payload does not match the selected paper IDs.",
        )

    def test_save_ideas_rejects_missing_source(self):
        response = self.client.post(
            "/papers/ideas/save",
            json={
                "title": "Missing source ideas",
                "paper_ids": [],
                "idea_result": self._make_idea_result(source_topic=None),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Provide at least one paper or topic to generate ideas.",
        )

    def test_ideas_service_and_router_do_not_import_provider_sdks(self):
        repo_root = Path(__file__).resolve().parents[2]
        checked_files = [
            repo_root / "backend/app/services/paper_ideas.py",
            repo_root / "backend/app/routers/ideas.py",
        ]
        forbidden_imports = (
            "import openai",
            "from openai",
            "import anthropic",
            "from anthropic",
            "import google",
            "from google",
            "import langchain",
            "from langchain",
            "import langgraph",
            "from langgraph",
        )

        for file_path in checked_files:
            content = file_path.read_text()
            for forbidden_import in forbidden_imports:
                self.assertNotIn(forbidden_import, content)

    def test_idea_generation_and_critique_use_workflow_model_settings(self):
        mock_client = Mock()
        mock_client.generate_structured.return_value = {"warnings": []}

        with (
            patch("app.services.paper_ideas.get_structured_client", return_value=mock_client),
            patch("app.services.paper_ideas.settings") as mock_settings,
        ):
            mock_settings.idea_generation_model = "idea-generation-test-model"
            mock_settings.idea_critique_model = "idea-critique-test-model"

            generate_candidate_ideas({"topic": "retrieval", "papers": []})
            critique_and_filter_ideas(
                {"topic": "retrieval", "papers": []},
                [make_idea(1)],
            )

        calls = mock_client.generate_structured.call_args_list
        self.assertEqual(calls[0].kwargs["model"], "idea-generation-test-model")
        self.assertEqual(calls[0].kwargs["schema_name"], "idea_candidates")
        self.assertEqual(calls[1].kwargs["model"], "idea-critique-test-model")
        self.assertEqual(calls[1].kwargs["schema_name"], "idea_critique")


if __name__ == "__main__":
    unittest.main()
