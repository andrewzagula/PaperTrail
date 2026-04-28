import uuid
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.llm.errors import (
    CONFIGURATION_ERROR_DETAIL,
    REQUEST_ERROR_DETAIL,
    ProviderConfigurationError,
    ProviderRequestError,
)
from app.main import app
from app.models.models import Paper, PaperSection, SavedItem, User
from app.services.paper_implementation import (
    IMPLEMENTATION_BREAKDOWN_FALLBACK_WARNING,
    IMPLEMENTATION_CODE_FALLBACK_WARNING,
    IMPLEMENTATION_CODE_FRAMEWORK_FALLBACK_WARNING,
    IMPLEMENTATION_CODE_NORMALIZATION_FALLBACK_WARNING,
    IMPLEMENTATION_EXTRACTION_FALLBACK_WARNING,
    IMPLEMENTATION_GAP_ANALYSIS_FALLBACK_WARNING,
    IMPLEMENTATION_PSEUDOCODE_FALLBACK_WARNING,
    IMPLEMENTATION_REVIEW_FALLBACK_WARNING,
    NO_ALGORITHM_STEPS_WARNING,
    NO_PARSED_SECTIONS_WARNING,
    SPARSE_METHOD_CONTEXT_WARNING,
    analyze_implementation_gaps,
    extract_algorithm_details,
    generate_implementation_pseudocode,
    generate_implementation_starter_code,
    review_implementation_scaffold,
)

DEFAULT_USER_EMAIL = "local@papertrail.dev"


class ImplementationsEndpointTests(unittest.TestCase):
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
        self.default_algorithm_payload = {
            "implementation_summary": "Extracted a grounded training outline.",
            "algorithm_steps": [
                {
                    "order": 1,
                    "title": "Prepare model inputs",
                    "description": "Collect the paper inputs described in the method.",
                    "inputs": ["Raw examples"],
                    "outputs": ["Model-ready tensors"],
                    "evidence": ["Method"],
                    "warnings": [],
                },
                {
                    "order": 2,
                    "title": "Run the training objective",
                    "description": "Optimize the model using the objective stated by the paper.",
                    "inputs": ["Model-ready tensors"],
                    "outputs": ["Trained model"],
                    "evidence": ["Method", "Experiments"],
                    "warnings": ["Exact hyperparameters are not fully specified."],
                },
            ],
            "warnings": ["Extraction should verify missing hyperparameters."],
        }
        self.default_gap_payload = {
            "assumptions_and_gaps": [
                {
                    "category": "hyperparameters",
                    "description": "Exact optimizer and learning-rate schedule are not fully specified.",
                    "severity": "medium",
                    "evidence": ["Experiments"],
                },
                {
                    "category": "equations",
                    "description": "The training objective should be verified against the paper equations.",
                    "severity": "medium",
                    "evidence": ["Method"],
                },
            ],
            "warnings": ["Gap analysis should verify objective details."],
        }
        self.default_pseudocode_payload = {
            "setup": "paper_inputs = load_method_inputs()\n# TODO: map paper data fields.",
            "model": "model = build_paper_model()\n# TODO: fill architecture from grounded steps.",
            "training_or_inference": "for batch in paper_inputs:\n    outputs = model(batch)\n    loss = compute_paper_objective(outputs, batch)",
            "evaluation": "metrics = compute_reported_metrics(outputs)\n# TODO: match paper metrics.",
            "extension_points": "# TODO: resolve hyperparameters before runnable code.",
            "warnings": ["Pseudocode contains TODO placeholders."],
        }
        self.default_code_payload = {
            "starter_code": [
                {
                    "path": "README.md",
                    "language": "markdown",
                    "purpose": "Explain the scaffold.",
                    "content": "# Implementation scaffold\n\nTODO: verify paper details.",
                },
                {
                    "path": "data.py",
                    "language": "python",
                    "purpose": "Load local data.",
                    "content": "def load_examples():\n    # TODO: load local data.\n    return []\n",
                },
                {
                    "path": "model.py",
                    "language": "python",
                    "purpose": "Define model placeholder.",
                    "content": "def build_model():\n    # TODO: fill architecture.\n    return None\n",
                },
            ],
            "setup_notes": ["Install local dependencies before running the scaffold."],
            "test_plan": ["Run python -m py_compile data.py model.py."],
            "warnings": ["Code generation produced starter TODOs."],
        }
        self.default_review_payload = {
            "warnings": ["Review warns this is not a verified reproduction."],
        }
        self.extract_algorithm_patch = patch(
            "app.services.paper_implementation.extract_algorithm_details",
            return_value=self.default_algorithm_payload,
        )
        self.mock_extract_algorithm = self.extract_algorithm_patch.start()
        self.analyze_gaps_patch = patch(
            "app.services.paper_implementation.analyze_implementation_gaps",
            return_value=self.default_gap_payload,
        )
        self.mock_analyze_gaps = self.analyze_gaps_patch.start()
        self.generate_pseudocode_patch = patch(
            "app.services.paper_implementation.generate_implementation_pseudocode",
            return_value=self.default_pseudocode_payload,
        )
        self.mock_generate_pseudocode = self.generate_pseudocode_patch.start()
        self.generate_code_patch = patch(
            "app.services.paper_implementation.generate_implementation_starter_code",
            return_value=self.default_code_payload,
        )
        self.mock_generate_code = self.generate_code_patch.start()
        self.review_scaffold_patch = patch(
            "app.services.paper_implementation.review_implementation_scaffold",
            return_value=self.default_review_payload,
        )
        self.mock_review_scaffold = self.review_scaffold_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.review_scaffold_patch.stop()
        self.generate_code_patch.stop()
        self.generate_pseudocode_patch.stop()
        self.analyze_gaps_patch.stop()
        self.extract_algorithm_patch.stop()
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
        title: str = "Implementation Paper",
        user_email: str = DEFAULT_USER_EMAIL,
        with_breakdown: bool = True,
        sections: list[tuple[str, str]] | None = None,
    ) -> str:
        user_id = self._get_or_create_user(user_email)

        with self.session_local() as db:
            structured_breakdown = None
            if with_breakdown:
                structured_breakdown = {
                    "problem": f"{title} problem",
                    "method": f"{title} method",
                    "results": f"{title} results",
                }

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

            paper_sections = sections
            if paper_sections is None:
                paper_sections = [
                    ("Abstract", f"{title} abstract section"),
                    ("Method", f"{title} method section"),
                    ("Related Work", f"{title} related work section"),
                    ("Experiments", f"{title} experiments section"),
                ]
            for order, (section_title, content) in enumerate(paper_sections):
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

    def _make_implementation_result(
        self,
        paper_id: str,
        paper_title: str = "Implementation Paper",
    ) -> dict:
        return {
            "paper": {
                "id": paper_id,
                "title": paper_title,
                "authors": f"{paper_title} Authors",
                "arxiv_url": f"https://arxiv.org/abs/{paper_title.replace(' ', '_')}",
                "created_at": "2026-04-27T00:00:00",
            },
            "source_sections": [
                {
                    "id": str(uuid.uuid4()),
                    "title": "Method",
                    "section_order": 1,
                    "content_preview": "Method details.",
                }
            ],
            "implementation_summary": "A grounded implementation scaffold.",
            "algorithm_steps": [
                {
                    "order": 1,
                    "title": "Prepare inputs",
                    "description": "Prepare paper inputs.",
                    "inputs": ["Raw examples"],
                    "outputs": ["Prepared examples"],
                    "evidence": ["Method"],
                }
            ],
            "assumptions_and_gaps": [
                {
                    "category": "hyperparameters",
                    "description": "Learning rate is not specified.",
                    "severity": "medium",
                    "evidence": ["Experiments"],
                }
            ],
            "pseudocode": "## Setup\nTODO: prepare inputs.",
            "starter_code": [
                {
                    "path": "README.md",
                    "language": "markdown",
                    "purpose": "Explain the scaffold.",
                    "content": "# Scaffold\n\nTODO: verify details.",
                },
                {
                    "path": "model.py",
                    "language": "python",
                    "purpose": "Model placeholder.",
                    "content": "def build_model():\n    return None\n",
                },
            ],
            "setup_notes": ["Install local dependencies."],
            "test_plan": ["Run python -m py_compile model.py."],
            "warnings": ["Starter scaffold only."],
        }

    def test_generate_implementation_returns_phase_9d_starter_code_contract(self):
        paper_id = self._create_paper()

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["paper"]["id"], paper_id)
        self.assertEqual(payload["paper"]["title"], "Implementation Paper")
        self.assertEqual(
            [section["title"] for section in payload["source_sections"]],
            ["Abstract", "Method", "Experiments"],
        )
        self.assertEqual(
            [step["title"] for step in payload["algorithm_steps"]],
            ["Prepare model inputs", "Run the training objective"],
        )
        self.assertEqual(payload["algorithm_steps"][0]["order"], 1)
        self.assertEqual(payload["algorithm_steps"][0]["evidence"], ["Method"])
        self.assertEqual(
            [gap["category"] for gap in payload["assumptions_and_gaps"]],
            ["hyperparameters", "equations"],
        )
        self.assertIn("## Setup", payload["pseudocode"])
        self.assertIn("## Model", payload["pseudocode"])
        self.assertIn("## Training / Inference", payload["pseudocode"])
        self.assertIn("## Evaluation", payload["pseudocode"])
        self.assertIn("## Extension Points", payload["pseudocode"])
        self.assertIn("paper_inputs = load_method_inputs()", payload["pseudocode"])
        self.assertEqual(
            [file["path"] for file in payload["starter_code"]],
            ["README.md", "data.py", "model.py"],
        )
        self.assertEqual(payload["starter_code"][1]["language"], "python")
        self.assertIn("TODO", payload["starter_code"][0]["content"])
        self.assertEqual(
            payload["setup_notes"],
            ["Install local dependencies before running the scaffold."],
        )
        self.assertEqual(
            payload["test_plan"],
            ["Run python -m py_compile data.py model.py."],
        )
        self.assertIn(
            "Extraction should verify missing hyperparameters.",
            payload["warnings"],
        )
        self.assertIn(
            "Run the training objective: Exact hyperparameters are not fully specified.",
            payload["warnings"],
        )
        self.assertIn("Gap analysis should verify objective details.", payload["warnings"])
        self.assertIn("Pseudocode contains TODO placeholders.", payload["warnings"])
        self.assertIn("Code generation produced starter TODOs.", payload["warnings"])
        self.assertIn(
            "Review warns this is not a verified reproduction.",
            payload["warnings"],
        )

    def test_generate_implementation_trims_focus(self):
        paper_id = self._create_paper()

        response = self.client.post(
            f"/papers/{paper_id}/implement",
            json={"focus": "  training loop only  "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Requested focus: training loop only.",
            response.json()["implementation_summary"],
        )
        user_message = self.mock_extract_algorithm.call_args.kwargs["focus"]
        self.assertEqual(user_message, "training loop only")
        self.assertEqual(
            self.mock_analyze_gaps.call_args.kwargs["focus"],
            "training loop only",
        )
        self.assertEqual(
            self.mock_generate_pseudocode.call_args.kwargs["focus"],
            "training loop only",
        )
        self.assertEqual(
            self.mock_generate_code.call_args.kwargs["focus"],
            "training loop only",
        )
        self.assertEqual(
            self.mock_review_scaffold.call_args.kwargs["focus"],
            "training loop only",
        )

    def test_generate_implementation_generates_missing_breakdown(self):
        paper_id = self._create_paper(with_breakdown=False)
        generated_breakdown = {
            "problem": "Generated problem",
            "method": "Generated method",
            "key_contributions": "Generated contributions",
            "results": "Generated results",
            "limitations": "Generated limitations",
            "future_work": "Generated future work",
        }

        with patch(
            "app.services.paper_implementation.analyze_paper",
            return_value=generated_breakdown,
        ) as mock_analyze:
            response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        mock_analyze.assert_called_once()
        with self.session_local() as db:
            paper = db.query(Paper).filter(Paper.id == uuid.UUID(paper_id)).one()
            self.assertEqual(paper.structured_breakdown["method"], "Generated method")

    def test_generate_implementation_warns_when_breakdown_generation_fails(self):
        paper_id = self._create_paper(
            with_breakdown=False,
            sections=[("Conclusion", "Only high level closing remarks are available.")],
        )

        with patch(
            "app.services.paper_implementation.analyze_paper",
            side_effect=RuntimeError("provider unavailable"),
        ):
            response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(IMPLEMENTATION_BREAKDOWN_FALLBACK_WARNING, payload["warnings"])
        self.assertIn(SPARSE_METHOD_CONTEXT_WARNING, payload["warnings"])

    def test_generate_implementation_sparse_method_context_feeds_fallback_gaps(self):
        paper_id = self._create_paper(
            with_breakdown=False,
            sections=[("Conclusion", "Only high level closing remarks are available.")],
        )
        self.mock_analyze_gaps.side_effect = RuntimeError("gap model failed")

        with patch(
            "app.services.paper_implementation.analyze_paper",
            side_effect=RuntimeError("provider unavailable"),
        ):
            response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        gap_descriptions = [
            gap["description"] for gap in payload["assumptions_and_gaps"]
        ]
        self.assertIn(SPARSE_METHOD_CONTEXT_WARNING, gap_descriptions)
        self.assertIn(IMPLEMENTATION_GAP_ANALYSIS_FALLBACK_WARNING, payload["warnings"])

    def test_generate_implementation_uses_deterministic_fallback_on_extraction_failure(
        self,
    ):
        paper_id = self._create_paper()
        self.mock_extract_algorithm.side_effect = RuntimeError("model failed")

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(IMPLEMENTATION_EXTRACTION_FALLBACK_WARNING, payload["warnings"])
        self.assertGreaterEqual(len(payload["algorithm_steps"]), 1)
        self.assertEqual(
            payload["algorithm_steps"][0]["title"],
            "Implement the described method",
        )

    def test_generate_implementation_uses_deterministic_gap_fallback_on_analysis_failure(
        self,
    ):
        paper_id = self._create_paper()
        self.mock_analyze_gaps.side_effect = RuntimeError("gap model failed")

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(IMPLEMENTATION_GAP_ANALYSIS_FALLBACK_WARNING, payload["warnings"])
        self.assertTrue(payload["assumptions_and_gaps"])
        self.assertIn(
            "hyperparameters",
            [gap["category"] for gap in payload["assumptions_and_gaps"]],
        )
        self.assertIn("## Extension Points", payload["pseudocode"])

    def test_generate_implementation_uses_deterministic_pseudocode_fallback_on_generation_failure(
        self,
    ):
        paper_id = self._create_paper()
        self.mock_generate_pseudocode.side_effect = RuntimeError("pseudo model failed")

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(IMPLEMENTATION_PSEUDOCODE_FALLBACK_WARNING, payload["warnings"])
        self.assertIn("## Setup", payload["pseudocode"])
        self.assertIn("## Training / Inference", payload["pseudocode"])
        self.assertIn("Run the training objective", payload["pseudocode"])
        self.assertIn("TODO [hyperparameters]", payload["pseudocode"])

    def test_generate_implementation_normalizes_malformed_algorithm_payload(self):
        paper_id = self._create_paper()
        self.mock_extract_algorithm.return_value = {
            "implementation_summary": "",
            "algorithm_steps": [
                {
                    "title": "Build model",
                    "description": "Construct the model components.",
                },
                {
                    "title": "Train model",
                    "description": "Optimize the objective.",
                    "inputs": ["Batches"],
                    "outputs": ["Weights"],
                },
            ],
            "warnings": ["Payload omitted some structured fields."],
        }

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [step["title"] for step in payload["algorithm_steps"]],
            ["Build model", "Train model"],
        )
        self.assertEqual(payload["algorithm_steps"][0]["inputs"], [
            "Not explicitly discussed in the provided paper context."
        ])
        self.assertIn("Payload omitted some structured fields.", payload["warnings"])
        self.assertIn(
            "Build model had no evidence references; available source context was attached.",
            payload["warnings"],
        )

    def test_generate_implementation_normalizes_malformed_gap_payload(self):
        paper_id = self._create_paper()
        self.mock_analyze_gaps.return_value = {
            "assumptions_and_gaps": [
                {
                    "category": "unknown",
                    "description": "Exact loss equation is missing.",
                    "severity": "critical",
                }
            ],
            "warnings": ["Gap payload omitted evidence."],
        }

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assumptions_and_gaps"][0]["category"], "equations")
        self.assertEqual(payload["assumptions_and_gaps"][0]["severity"], "high")
        self.assertTrue(payload["assumptions_and_gaps"][0]["evidence"])
        self.assertIn("Gap payload omitted evidence.", payload["warnings"])
        self.assertIn(
            "Exact loss equation is missing. had no evidence references; available source context was attached.",
            payload["warnings"],
        )

    def test_generate_implementation_normalizes_malformed_pseudocode_payload(self):
        paper_id = self._create_paper()
        self.mock_generate_pseudocode.return_value = {
            "setup": "custom_setup()",
            "warnings": ["Pseudocode payload omitted some sections."],
        }

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("## Setup\ncustom_setup()", payload["pseudocode"])
        self.assertIn("## Model", payload["pseudocode"])
        self.assertIn("## Training / Inference", payload["pseudocode"])
        self.assertIn(
            "Pseudocode payload omitted some sections.",
            payload["warnings"],
        )

    def test_generate_implementation_supports_generic_python_starter_code(self):
        paper_id = self._create_paper()
        self.mock_generate_code.return_value = {
            "starter_code": [
                {
                    "path": "README.md",
                    "language": "markdown",
                    "purpose": "Explain generic scaffold.",
                    "content": "# Generic scaffold\n\nTODO: fill details.",
                },
                {
                    "path": "pipeline.py",
                    "language": "python",
                    "purpose": "Pipeline placeholder.",
                    "content": "def run_pipeline():\n    # TODO: fill steps.\n    return []\n",
                },
                {
                    "path": "tests_smoke.py",
                    "language": "python",
                    "purpose": "Smoke checks.",
                    "content": "def test_placeholder():\n    assert True\n",
                },
            ],
            "setup_notes": ["Use the standard library scaffold first."],
            "test_plan": ["Run python -m py_compile pipeline.py tests_smoke.py."],
            "warnings": [],
        }

        response = self.client.post(
            f"/papers/{paper_id}/implement",
            json={"target_framework": "generic-python"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [file["path"] for file in payload["starter_code"]],
            ["README.md", "pipeline.py", "tests_smoke.py"],
        )
        self.assertEqual(
            self.mock_generate_code.call_args.kwargs["target_framework"],
            "generic-python",
        )
        self.assertEqual(
            self.mock_review_scaffold.call_args.kwargs["target_framework"],
            "generic-python",
        )

    def test_generate_implementation_falls_back_when_generic_python_payload_uses_pytorch(
        self,
    ):
        paper_id = self._create_paper()
        self.mock_generate_code.return_value = {
            "starter_code": [
                {
                    "path": "pytorch/README.md",
                    "language": "markdown",
                    "purpose": "Explain PyTorch scaffold.",
                    "content": "# PyTorch scaffold\n\nTODO: fill details.",
                },
                {
                    "path": "pytorch/model.py",
                    "language": "python",
                    "purpose": "PyTorch model.",
                    "content": "import torch\n\nclass Model:\n    pass\n",
                },
            ],
            "setup_notes": ["Install PyTorch before running."],
            "test_plan": ["Run PyTorch model checks."],
            "warnings": [],
        }

        response = self.client.post(
            f"/papers/{paper_id}/implement",
            json={"target_framework": "generic-python"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [file["path"] for file in payload["starter_code"]],
            ["README.md", "data.py", "pipeline.py", "tests_smoke.py"],
        )
        self.assertTrue(
            all(
                "pytorch" not in file["content"].lower()
                for file in payload["starter_code"]
            )
        )
        self.assertEqual(
            payload["setup_notes"],
            [
                "Generated files are starter scaffold text only; PaperTrail does not write them to disk or execute them.",
                "Resolve every TODO against the original paper before treating the scaffold as runnable.",
                "The generic Python scaffold avoids framework-specific dependencies by default.",
            ],
        )
        self.assertIn(
            IMPLEMENTATION_CODE_FRAMEWORK_FALLBACK_WARNING,
            payload["warnings"],
        )

    def test_generate_implementation_uses_deterministic_code_fallback_on_generation_failure(
        self,
    ):
        paper_id = self._create_paper()
        self.mock_generate_code.side_effect = RuntimeError("code model failed")

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(IMPLEMENTATION_CODE_FALLBACK_WARNING, payload["warnings"])
        self.assertEqual(
            [file["path"] for file in payload["starter_code"]],
            ["README.md", "data.py", "model.py", "train.py"],
        )
        self.assertIn("TODO", payload["starter_code"][0]["content"])

    def test_generate_implementation_normalizes_malformed_code_payload(self):
        paper_id = self._create_paper()
        self.mock_generate_code.return_value = {
            "starter_code": [
                {
                    "path": "/absolute.py",
                    "language": "python",
                    "purpose": "Bad path.",
                    "content": "def bad():\n    return None\n",
                },
                {
                    "path": "../escape.py",
                    "language": "python",
                    "purpose": "Bad path.",
                    "content": "def bad():\n    return None\n",
                },
                {
                    "path": ".hidden.py",
                    "language": "python",
                    "purpose": "Hidden path.",
                    "content": "def hidden():\n    return None\n",
                },
                {
                    "path": "notes.txt",
                    "language": "text",
                    "purpose": "Unsupported extension.",
                    "content": "TODO",
                },
                {
                    "path": "pipeline.py",
                    "language": "not-used",
                    "purpose": "Valid pipeline.",
                    "content": "def run_pipeline():\n    # TODO: fill paper details.\n    return []\n",
                },
                {
                    "path": "pipeline.py",
                    "language": "python",
                    "purpose": "Duplicate.",
                    "content": "def duplicate():\n    return []\n",
                },
            ],
            "setup_notes": [],
            "test_plan": [],
            "warnings": ["Malformed code payload omitted supporting notes."],
        }

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        paths = [file["path"] for file in payload["starter_code"]]
        self.assertIn("pipeline.py", paths)
        self.assertGreaterEqual(len(paths), 2)
        self.assertNotIn("/absolute.py", paths)
        self.assertNotIn("../escape.py", paths)
        self.assertNotIn(".hidden.py", paths)
        self.assertNotIn("notes.txt", paths)
        self.assertIn("Malformed code payload omitted supporting notes.", payload["warnings"])
        self.assertIn(
            "Starter code file skipped because path was absolute: /absolute.py.",
            payload["warnings"],
        )
        self.assertIn(
            "Starter code file skipped because path was unsafe: ../escape.py.",
            payload["warnings"],
        )
        self.assertIn(
            "Starter code file skipped because hidden paths are not allowed: .hidden.py.",
            payload["warnings"],
        )
        self.assertIn(
            "Starter code file skipped because extension is unsupported: notes.txt.",
            payload["warnings"],
        )

    def test_generate_implementation_replaces_invalid_python_starter_file(self):
        paper_id = self._create_paper()
        self.mock_generate_code.return_value = {
            "starter_code": [
                {
                    "path": "model.py",
                    "language": "python",
                    "purpose": "Invalid Python.",
                    "content": "def broken(:\n    pass\n",
                },
                {
                    "path": "README.md",
                    "language": "markdown",
                    "purpose": "Readme.",
                    "content": "# Scaffold\n\nTODO: verify details.",
                },
            ],
            "setup_notes": ["Setup note."],
            "test_plan": ["Test note."],
            "warnings": [],
        }

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        model_file = next(
            file for file in payload["starter_code"] if file["path"] == "model.py"
        )
        self.assertIn("Safe placeholder for model.py", model_file["content"])
        self.assertIn(
            "model.py was replaced because generated Python did not parse.",
            payload["warnings"],
        )

    def test_generate_implementation_replaces_unsafe_starter_code(self):
        paper_id = self._create_paper()
        self.mock_generate_code.return_value = {
            "starter_code": [
                {
                    "path": "data.py",
                    "language": "python",
                    "purpose": "Unsafe data loading.",
                    "content": "import requests\n\ndef load():\n    return requests.get('https://example.com').text\n",
                },
                {
                    "path": "model.py",
                    "language": "python",
                    "purpose": "Model.",
                    "content": "def build_model():\n    # TODO: fill architecture.\n    return None\n",
                },
            ],
            "setup_notes": ["Setup note."],
            "test_plan": ["Test note."],
            "warnings": [],
        }

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        data_file = next(
            file for file in payload["starter_code"] if file["path"] == "data.py"
        )
        self.assertIn("Safe placeholder for data.py", data_file["content"])
        self.assertNotIn("requests.get", data_file["content"])
        self.assertIn(
            "data.py was replaced because starter code contained unsafe or out-of-scope behavior: network calls.",
            payload["warnings"],
        )

    def test_generate_implementation_uses_deterministic_review_on_review_failure(self):
        paper_id = self._create_paper()
        self.mock_review_scaffold.side_effect = RuntimeError("review model failed")

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            IMPLEMENTATION_REVIEW_FALLBACK_WARNING,
            response.json()["warnings"],
        )

    def test_generate_implementation_uses_code_fallback_when_no_files_are_usable(self):
        paper_id = self._create_paper()
        self.mock_generate_code.return_value = {
            "starter_code": [
                {
                    "path": "oversized.py",
                    "language": "python",
                    "purpose": "Too large.",
                    "content": "x = 1\n" * 3000,
                }
            ],
            "setup_notes": [],
            "test_plan": [],
            "warnings": [],
        }

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [file["path"] for file in payload["starter_code"]],
            ["README.md", "data.py", "model.py", "train.py"],
        )
        self.assertIn(
            IMPLEMENTATION_CODE_NORMALIZATION_FALLBACK_WARNING,
            payload["warnings"],
        )

    def test_generate_implementation_with_no_sections_returns_grounding_warnings(self):
        paper_id = self._create_paper(with_breakdown=False, sections=[])

        with patch(
            "app.services.paper_implementation.analyze_paper",
            side_effect=RuntimeError("provider unavailable"),
        ):
            response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_sections"], [])
        self.assertEqual(payload["algorithm_steps"], [])
        self.assertTrue(payload["assumptions_and_gaps"])
        self.assertIn("## Setup", payload["pseudocode"])
        self.assertIn("No grounded algorithm steps were available", payload["pseudocode"])
        self.assertIn(NO_PARSED_SECTIONS_WARNING, payload["warnings"])
        self.assertIn(NO_ALGORITHM_STEPS_WARNING, payload["warnings"])
        self.mock_extract_algorithm.assert_not_called()
        self.mock_analyze_gaps.assert_not_called()
        self.mock_generate_pseudocode.assert_not_called()
        self.mock_generate_code.assert_not_called()
        self.mock_review_scaffold.assert_not_called()
        self.assertEqual(
            [file["path"] for file in payload["starter_code"]],
            ["README.md", "data.py", "model.py", "train.py"],
        )
        self.assertIn("TODO", payload["starter_code"][0]["content"])

    def test_generate_implementation_rejects_invalid_uuid(self):
        response = self.client.post("/papers/not-a-uuid/implement", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid paper ID: not-a-uuid")

    def test_generate_implementation_rejects_missing_paper(self):
        missing_id = str(uuid.uuid4())

        response = self.client.post(f"/papers/{missing_id}/implement", json={})

        self.assertEqual(response.status_code, 404)
        self.assertIn(missing_id, response.json()["detail"])

    def test_generate_implementation_rejects_wrong_user_paper(self):
        paper_id = self._create_paper(user_email="other@papertrail.dev")

        response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 404)
        self.assertIn(paper_id, response.json()["detail"])

    def test_generate_implementation_rejects_focus_over_limit(self):
        paper_id = self._create_paper()

        response = self.client.post(
            f"/papers/{paper_id}/implement",
            json={"focus": "x" * 1001},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Implementation focus must be 1000 characters or fewer.",
        )

    def test_generate_implementation_rejects_unsupported_target_language(self):
        paper_id = self._create_paper()

        response = self.client.post(
            f"/papers/{paper_id}/implement",
            json={"target_language": "typescript"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Unsupported target language. Supported values: python.",
        )

    def test_generate_implementation_rejects_unsupported_target_framework(self):
        paper_id = self._create_paper()

        response = self.client.post(
            f"/papers/{paper_id}/implement",
            json={"target_framework": "tensorflow"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Unsupported target framework. Supported values: pytorch, generic-python.",
        )

    def test_save_implementation_persists_result_without_rerunning_generation(self):
        paper_id = self._create_paper()
        generate_response = self.client.post(f"/papers/{paper_id}/implement", json={})
        self.assertEqual(generate_response.status_code, 200)
        implementation_payload = generate_response.json()
        self.assertEqual(self.mock_extract_algorithm.call_count, 1)
        self.assertEqual(self.mock_analyze_gaps.call_count, 1)
        self.assertEqual(self.mock_generate_pseudocode.call_count, 1)
        self.assertEqual(self.mock_generate_code.call_count, 1)
        self.assertEqual(self.mock_review_scaffold.call_count, 1)

        with (
            patch("app.services.paper_implementation.analyze_paper") as mock_analyze,
            patch("app.services.paper_implementation.build_implementation_graph") as mock_build_graph,
        ):
            response = self.client.post(
                f"/papers/{paper_id}/implement/save",
                json={
                    "title": "  Implementation scaffold  ",
                    "implementation": implementation_payload,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mock_extract_algorithm.call_count, 1)
        self.assertEqual(self.mock_analyze_gaps.call_count, 1)
        self.assertEqual(self.mock_generate_pseudocode.call_count, 1)
        self.assertEqual(self.mock_generate_code.call_count, 1)
        self.assertEqual(self.mock_review_scaffold.call_count, 1)
        mock_analyze.assert_not_called()
        mock_build_graph.assert_not_called()

        payload = response.json()
        self.assertEqual(payload["title"], "Implementation scaffold")
        self.assertEqual(payload["item_type"], "implementation")
        self.assertEqual(payload["paper_ids"], [paper_id])
        self.assertTrue(payload["created_at"])

        saved_item = self._fetch_saved_item(payload["id"])
        self.assertIsNotNone(saved_item)
        self.assertEqual(saved_item["title"], "Implementation scaffold")
        self.assertEqual(saved_item["item_type"], "implementation")
        self.assertEqual(saved_item["paper_ids"], [paper_id])
        self.assertEqual(saved_item["data"], implementation_payload)

    def test_save_implementation_rejects_blank_title(self):
        paper_id = self._create_paper()

        response = self.client.post(
            f"/papers/{paper_id}/implement/save",
            json={
                "title": "   ",
                "implementation": self._make_implementation_result(paper_id),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Implementation title is required.",
        )

    def test_save_implementation_rejects_title_over_limit(self):
        paper_id = self._create_paper()

        response = self.client.post(
            f"/papers/{paper_id}/implement/save",
            json={
                "title": "x" * 1001,
                "implementation": self._make_implementation_result(paper_id),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Implementation title must be 1000 characters or fewer.",
        )

    def test_save_implementation_rejects_invalid_uuid(self):
        response = self.client.post(
            "/papers/not-a-uuid/implement/save",
            json={
                "title": "Implementation scaffold",
                "implementation": self._make_implementation_result(str(uuid.uuid4())),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid paper ID: not-a-uuid")

    def test_save_implementation_rejects_missing_paper(self):
        missing_id = str(uuid.uuid4())

        response = self.client.post(
            f"/papers/{missing_id}/implement/save",
            json={
                "title": "Implementation scaffold",
                "implementation": self._make_implementation_result(missing_id),
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn(missing_id, response.json()["detail"])

    def test_save_implementation_rejects_wrong_user_paper(self):
        paper_id = self._create_paper(user_email="other@papertrail.dev")

        response = self.client.post(
            f"/papers/{paper_id}/implement/save",
            json={
                "title": "Implementation scaffold",
                "implementation": self._make_implementation_result(paper_id),
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn(paper_id, response.json()["detail"])

    def test_save_implementation_rejects_payload_paper_id_mismatch(self):
        paper_id = self._create_paper()
        other_id = str(uuid.uuid4())

        response = self.client.post(
            f"/papers/{paper_id}/implement/save",
            json={
                "title": "Implementation scaffold",
                "implementation": self._make_implementation_result(other_id),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Implementation payload does not match the selected paper.",
        )

    def test_save_implementation_rejects_payload_paper_title_mismatch(self):
        paper_id = self._create_paper()

        response = self.client.post(
            f"/papers/{paper_id}/implement/save",
            json={
                "title": "Implementation scaffold",
                "implementation": self._make_implementation_result(
                    paper_id,
                    paper_title="Different Paper",
                ),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Implementation payload does not match the selected paper.",
        )

    def test_generate_implementation_maps_provider_request_error(self):
        paper_id = str(uuid.uuid4())

        with patch(
            "app.routers.implementations.generate_paper_implementation",
            side_effect=ProviderRequestError("provider request failed"),
        ):
            response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], REQUEST_ERROR_DETAIL)

    def test_generate_implementation_maps_provider_configuration_error(self):
        paper_id = str(uuid.uuid4())

        with patch(
            "app.routers.implementations.generate_paper_implementation",
            side_effect=ProviderConfigurationError("provider not configured"),
        ):
            response = self.client.post(f"/papers/{paper_id}/implement", json={})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], CONFIGURATION_ERROR_DETAIL)

    def test_implementation_generation_helpers_use_workflow_model_settings(self):
        mock_client = Mock()
        mock_client.generate_structured.return_value = {"warnings": []}
        implementation_context = {
            "paper": {"title": "Implementation Paper"},
            "structured_breakdown": {"method": "Grounded method"},
            "relevant_sections": [{"title": "Method", "content": "Method details."}],
        }
        algorithm_steps = [
            {
                "order": 1,
                "title": "Prepare inputs",
                "description": "Prepare data.",
                "inputs": ["Raw data"],
                "outputs": ["Prepared data"],
                "evidence": ["Method"],
            }
        ]
        assumptions_and_gaps = [
            {
                "category": "hyperparameters",
                "description": "Learning rate is unspecified.",
                "severity": "medium",
                "evidence": ["Experiments"],
            }
        ]
        starter_code = [
            {
                "path": "model.py",
                "language": "python",
                "purpose": "Model placeholder.",
                "content": "def build_model():\n    return None\n",
            }
        ]

        with (
            patch(
                "app.services.paper_implementation.get_structured_client",
                return_value=mock_client,
            ),
            patch("app.services.paper_implementation.settings") as mock_settings,
        ):
            mock_settings.implementation_extraction_model = (
                "implementation-extraction-test-model"
            )
            mock_settings.implementation_code_model = (
                "implementation-code-test-model"
            )
            mock_settings.implementation_review_model = (
                "implementation-review-test-model"
            )

            extract_algorithm_details(
                implementation_context=implementation_context,
                focus="training loop",
                target_framework="pytorch",
            )
            analyze_implementation_gaps(
                implementation_context=implementation_context,
                algorithm_steps=algorithm_steps,
                warnings=[],
                focus="training loop",
                target_framework="pytorch",
            )
            generate_implementation_pseudocode(
                implementation_context=implementation_context,
                algorithm_steps=algorithm_steps,
                assumptions_and_gaps=assumptions_and_gaps,
                focus="training loop",
                target_framework="pytorch",
            )
            generate_implementation_starter_code(
                implementation_context=implementation_context,
                algorithm_steps=algorithm_steps,
                assumptions_and_gaps=assumptions_and_gaps,
                pseudocode="## Setup\nprepare inputs",
                focus="training loop",
                target_language="python",
                target_framework="pytorch",
            )
            review_implementation_scaffold(
                implementation_context=implementation_context,
                algorithm_steps=algorithm_steps,
                assumptions_and_gaps=assumptions_and_gaps,
                pseudocode="## Setup\nprepare inputs",
                starter_code=starter_code,
                focus="training loop",
                target_framework="pytorch",
            )

        self.assertEqual(
            [
                call.kwargs["model"]
                for call in mock_client.generate_structured.call_args_list
            ],
            [
                "implementation-extraction-test-model",
                "implementation-extraction-test-model",
                "implementation-extraction-test-model",
                "implementation-code-test-model",
                "implementation-review-test-model",
            ],
        )

    def test_implementation_service_and_router_do_not_import_provider_sdks(self):
        repo_root = Path(__file__).resolve().parents[2]
        checked_files = [
            repo_root / "backend/app/services/paper_implementation.py",
            repo_root / "backend/app/routers/implementations.py",
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


if __name__ == "__main__":
    unittest.main()
