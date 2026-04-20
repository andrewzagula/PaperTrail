import uuid
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Paper, PaperSection, SavedItem, User
from app.services.paper_compare import NOT_EXPLICITLY_DISCUSSED

DEFAULT_USER_EMAIL = "local@papertrail.dev"


def make_breakdown(label: str) -> dict:
    return {
        "problem": f"{label} problem",
        "method": f"{label} method",
        "key_contributions": f"{label} strengths",
        "results": f"{label} results",
        "limitations": f"{label} weaknesses",
        "future_work": f"{label} future work",
    }


def make_compare_payload(label: str) -> dict:
    return {
        "problem": f"{label} compare problem",
        "method": f"{label} compare method",
        "dataset_or_eval_setup": f"{label} evaluation setup",
        "key_results": f"{label} compare results",
        "strengths": f"{label} compare strengths",
        "weaknesses": f"{label} compare weaknesses",
        "evidence_notes": {
            "problem": [f"{label} Abstract"],
            "method": [f"{label} Method", f"{label} Experiments"],
            "dataset_or_eval_setup": [f"{label} Experiments"],
            "key_results": [f"{label} Results"],
            "strengths": [f"{label} Discussion"],
            "weaknesses": [f"{label} Limitations"],
        },
        "warnings": [],
    }


def make_compare_synthesis(
    *,
    problem_landscape: str = (
        "These papers all target the same broad research problem from different angles."
    ),
    method_divergence: str = (
        "The methods diverge in modeling assumptions, optimization strategy, and system design."
    ),
    evaluation_differences: str = (
        "The evaluation setups differ in datasets, benchmarks, and reporting detail."
    ),
    researcher_tradeoffs: str = (
        "The main tradeoff is between stronger empirical performance and narrower applicability."
    ),
    warnings: list[str] | None = None,
) -> dict:
    return {
        "problem_landscape": problem_landscape,
        "method_divergence": method_divergence,
        "evaluation_differences": evaluation_differences,
        "researcher_tradeoffs": researcher_tradeoffs,
        "warnings": warnings or [],
    }


class CompareEndpointTests(unittest.TestCase):
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
        self.synthesis_patch = patch(
            "app.services.paper_compare.generate_comparison_synthesis",
            return_value=make_compare_synthesis(),
        )
        self.mock_generate_synthesis = self.synthesis_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.synthesis_patch.stop()
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
        user_email: str = DEFAULT_USER_EMAIL,
    ) -> str:
        user_id = self._get_or_create_user(user_email)

        with self.session_local() as db:
            paper = Paper(
                user_id=uuid.UUID(user_id),
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

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_compare_returns_structured_summary_and_matrix_for_three_papers(
        self,
        mock_extract,
    ):
        paper_ids = [
            self._create_paper("Paper One", breakdown=make_breakdown("one")),
            self._create_paper("Paper Two", breakdown=make_breakdown("two")),
            self._create_paper("Paper Three", breakdown=make_breakdown("three")),
        ]
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("two"),
            make_compare_payload("three"),
        ]
        self.mock_generate_synthesis.return_value = make_compare_synthesis(
            problem_landscape=(
                "Paper One, Paper Two, and Paper Three all target robust long-context reasoning."
            ),
            method_divergence=(
                "Paper One emphasizes retrieval, Paper Two emphasizes architectural changes, and "
                "Paper Three emphasizes training-time supervision."
            ),
            evaluation_differences=(
                "The papers compare on different benchmarks, so direct score comparisons need caution."
            ),
            researcher_tradeoffs=(
                "The strongest tradeoff is between broader applicability and tighter benchmark wins."
            ),
            warnings=["Benchmark overlap is incomplete across the selected papers."],
        )

        response = self.client.post("/papers/compare", json={"paper_ids": paper_ids})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["selected_papers"]), 3)
        self.assertEqual(len(payload["normalized_profiles"]), 3)
        self.assertEqual(len(payload["comparison_table"]["columns"]), 4)
        self.assertEqual(len(payload["comparison_table"]["rows"]), 6)
        self.assertEqual(
            len(payload["comparison_table"]["rows"][0]["values"]),
            3,
        )
        self.assertEqual(
            payload["normalized_profiles"][0]["evidence_notes"]["method"],
            ["one Method", "one Experiments"],
        )
        self.assertIn("What the papers are trying to solve:", payload["narrative_summary"])
        self.assertIn("Where the methods diverge:", payload["narrative_summary"])
        self.assertIn("How evaluation differs:", payload["narrative_summary"])
        self.assertIn("Researcher tradeoffs:", payload["narrative_summary"])
        self.assertIn("Benchmark overlap is incomplete", payload["warnings"][0])

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_compare_supports_five_papers(self, mock_extract):
        paper_ids = [
            self._create_paper(f"Paper {index}", breakdown=make_breakdown(str(index)))
            for index in range(5)
        ]
        mock_extract.side_effect = [
            make_compare_payload(str(index))
            for index in range(5)
        ]

        response = self.client.post("/papers/compare", json={"paper_ids": paper_ids})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["selected_papers"]), 5)
        self.assertEqual(len(payload["comparison_table"]["columns"]), 6)
        for row in payload["comparison_table"]["rows"]:
            self.assertEqual(len(row["values"]), 5)

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_compare_surfaces_missing_info_as_warnings(self, mock_extract):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        paper_two = self._create_paper("Paper Two", breakdown=make_breakdown("two"))
        mock_extract.side_effect = [
            {
                **make_compare_payload("one"),
                "dataset_or_eval_setup": NOT_EXPLICITLY_DISCUSSED,
                "key_results": NOT_EXPLICITLY_DISCUSSED,
            },
            make_compare_payload("two"),
        ]
        self.mock_generate_synthesis.return_value = make_compare_synthesis(
            warnings=["Evaluation coverage is uneven across the selected papers."]
        )

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one, paper_two]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["normalized_profiles"][0]["dataset_or_eval_setup"],
            NOT_EXPLICITLY_DISCUSSED,
        )
        self.assertTrue(
            any(
                "Paper One: Dataset / Eval Setup was not explicitly discussed in the paper."
                in warning
                for warning in payload["warnings"]
            )
        )
        self.assertTrue(
            any(
                "Paper One: Key Results was not explicitly discussed in the paper."
                in warning
                for warning in payload["warnings"]
            )
        )
        self.assertTrue(
            any(
                "Evaluation coverage is uneven across the selected papers." in warning
                for warning in payload["warnings"]
            )
        )

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_compare_normalizes_legacy_list_evidence_notes(self, mock_extract):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        paper_two = self._create_paper("Paper Two", breakdown=make_breakdown("two"))
        mock_extract.side_effect = [
            {
                **make_compare_payload("one"),
                "evidence_notes": ["method: Abstract, Method", "key_results: Results"],
            },
            make_compare_payload("two"),
        ]

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one, paper_two]},
        )

        self.assertEqual(response.status_code, 200)
        evidence_notes = response.json()["normalized_profiles"][0]["evidence_notes"]
        self.assertEqual(evidence_notes["method"], ["Abstract", "Method"])
        self.assertEqual(evidence_notes["key_results"], ["Results"])

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_compare_uses_breakdown_fallback_when_profile_extraction_fails(
        self,
        mock_extract,
    ):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        paper_two = self._create_paper("Paper Two", breakdown=make_breakdown("two"))
        mock_extract.side_effect = [
            RuntimeError("boom"),
            make_compare_payload("two"),
        ]

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one, paper_two]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["normalized_profiles"][0]["method"],
            "one method",
        )
        self.assertTrue(
            any(
                "Paper One: Compare profile extraction fell back to stored paper analysis"
                in warning
                for warning in payload["warnings"]
            )
        )

    @patch("app.services.paper_compare.extract_compare_profile_details")
    @patch("app.services.paper_compare.analyze_paper")
    def test_compare_analyzes_missing_breakdown_on_demand(
        self,
        mock_analyze_paper,
        mock_extract,
    ):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        paper_two = self._create_paper("Paper Two", breakdown=None)

        mock_analyze_paper.return_value = make_breakdown("generated")
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("generated"),
        ]

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one, paper_two]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_analyze_paper.call_count, 1)
        self.assertEqual(
            self._fetch_paper_breakdown(paper_two),
            make_breakdown("generated"),
        )

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_compare_uses_deterministic_summary_fallback_when_synthesis_fails(
        self,
        mock_extract,
    ):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        paper_two = self._create_paper("Paper Two", breakdown=make_breakdown("two"))
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("two"),
        ]
        self.mock_generate_synthesis.side_effect = RuntimeError("summary down")

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one, paper_two]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("What the papers are trying to solve:", payload["narrative_summary"])
        self.assertIn("Paper One:", payload["narrative_summary"])
        self.assertIn("Paper Two:", payload["narrative_summary"])
        self.assertTrue(
            any(
                "Cross-paper narrative summary used deterministic fallback" in warning
                for warning in payload["warnings"]
            )
        )

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_save_comparison_persists_rendered_result_without_rerunning_compare(
        self,
        mock_extract,
    ):
        paper_ids = [
            self._create_paper("Paper One", breakdown=make_breakdown("one")),
            self._create_paper("Paper Two", breakdown=make_breakdown("two")),
        ]
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("two"),
        ]

        compare_response = self.client.post("/papers/compare", json={"paper_ids": paper_ids})
        self.assertEqual(compare_response.status_code, 200)
        compare_payload = compare_response.json()
        self.assertEqual(self.mock_generate_synthesis.call_count, 1)

        save_response = self.client.post(
            "/papers/compare/save",
            json={
                "title": "  Long Context Retrieval Comparison  ",
                "paper_ids": paper_ids,
                "comparison": compare_payload,
            },
        )

        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(self.mock_generate_synthesis.call_count, 1)

        payload = save_response.json()
        self.assertEqual(payload["title"], "Long Context Retrieval Comparison")
        self.assertEqual(payload["item_type"], "comparison")
        self.assertEqual(payload["paper_ids"], paper_ids)
        self.assertTrue(payload["created_at"])

        saved_item = self._fetch_saved_item(payload["id"])
        self.assertIsNotNone(saved_item)
        self.assertEqual(saved_item["title"], "Long Context Retrieval Comparison")
        self.assertEqual(saved_item["item_type"], "comparison")
        self.assertEqual(saved_item["paper_ids"], paper_ids)
        self.assertEqual(saved_item["data"], compare_payload)

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_save_comparison_rejects_blank_title(self, mock_extract):
        paper_ids = [
            self._create_paper("Paper One", breakdown=make_breakdown("one")),
            self._create_paper("Paper Two", breakdown=make_breakdown("two")),
        ]
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("two"),
        ]
        comparison = self.client.post("/papers/compare", json={"paper_ids": paper_ids}).json()

        response = self.client.post(
            "/papers/compare/save",
            json={
                "title": "   ",
                "paper_ids": paper_ids,
                "comparison": comparison,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Comparison title is required.")

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_save_comparison_rejects_title_over_limit(self, mock_extract):
        paper_ids = [
            self._create_paper("Paper One", breakdown=make_breakdown("one")),
            self._create_paper("Paper Two", breakdown=make_breakdown("two")),
        ]
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("two"),
        ]
        comparison = self.client.post("/papers/compare", json={"paper_ids": paper_ids}).json()

        response = self.client.post(
            "/papers/compare/save",
            json={
                "title": "x" * 1001,
                "paper_ids": paper_ids,
                "comparison": comparison,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Comparison title must be 1000 characters or fewer.",
        )

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_save_comparison_rejects_invalid_uuid(self, mock_extract):
        valid_paper = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        other_paper = self._create_paper("Paper Two", breakdown=make_breakdown("two"))
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("two"),
        ]
        comparison = self.client.post(
            "/papers/compare",
            json={"paper_ids": [valid_paper, other_paper]},
        ).json()

        response = self.client.post(
            "/papers/compare/save",
            json={
                "title": "Invalid UUID comparison",
                "paper_ids": [valid_paper, "not-a-uuid"],
                "comparison": comparison,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid paper ID: not-a-uuid")

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_save_comparison_rejects_duplicate_ids(self, mock_extract):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        paper_two = self._create_paper("Paper Two", breakdown=make_breakdown("two"))
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("two"),
        ]
        comparison = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one, paper_two]},
        ).json()

        response = self.client.post(
            "/papers/compare/save",
            json={
                "title": "Duplicate comparison",
                "paper_ids": [paper_one, paper_two, paper_one],
                "comparison": comparison,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Duplicate paper IDs are not allowed.")

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_save_comparison_rejects_missing_paper(self, mock_extract):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        paper_two = self._create_paper("Paper Two", breakdown=make_breakdown("two"))
        missing_id = str(uuid.uuid4())
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("two"),
        ]
        comparison = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one, paper_two]},
        ).json()

        response = self.client.post(
            "/papers/compare/save",
            json={
                "title": "Missing paper comparison",
                "paper_ids": [paper_one, missing_id],
                "comparison": comparison,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn(missing_id, response.json()["detail"])

    @patch("app.services.paper_compare.extract_compare_profile_details")
    def test_save_comparison_rejects_selected_paper_mismatch(self, mock_extract):
        paper_ids = [
            self._create_paper("Paper One", breakdown=make_breakdown("one")),
            self._create_paper("Paper Two", breakdown=make_breakdown("two")),
        ]
        mock_extract.side_effect = [
            make_compare_payload("one"),
            make_compare_payload("two"),
        ]
        comparison = self.client.post("/papers/compare", json={"paper_ids": paper_ids}).json()
        comparison["selected_papers"] = list(reversed(comparison["selected_papers"]))

        response = self.client.post(
            "/papers/compare/save",
            json={
                "title": "Mismatched comparison",
                "paper_ids": paper_ids,
                "comparison": comparison,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Comparison payload does not match the selected paper IDs.",
        )

    def test_compare_rejects_too_few_papers(self):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Select at least 2 papers to compare.")

    def test_compare_rejects_too_many_papers(self):
        paper_ids = [
            self._create_paper(f"Paper {index}", breakdown=make_breakdown(str(index)))
            for index in range(6)
        ]

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": paper_ids},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "You can compare up to 5 papers at a time.")

    def test_compare_rejects_duplicate_ids(self):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        paper_two = self._create_paper("Paper Two", breakdown=make_breakdown("two"))

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one, paper_two, paper_one]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Duplicate paper IDs are not allowed.")

    def test_compare_rejects_invalid_uuid(self):
        valid_paper = self._create_paper("Paper One", breakdown=make_breakdown("one"))

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": [valid_paper, "not-a-uuid"]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid paper ID: not-a-uuid")

    def test_compare_rejects_missing_paper(self):
        paper_one = self._create_paper("Paper One", breakdown=make_breakdown("one"))
        missing_id = str(uuid.uuid4())

        response = self.client.post(
            "/papers/compare",
            json={"paper_ids": [paper_one, missing_id]},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn(missing_id, response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
