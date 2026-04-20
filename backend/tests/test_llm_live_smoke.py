import importlib.util
import os
import unittest
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from app.config import settings
from app.llm.factory import get_chat_client, get_embedding_client, get_structured_client
from app.services.analyzer import analyze_paper
from app.services.discovery import generate_search_queries
from app.services.embedder import generate_query_embedding
from app.services.paper_compare import generate_comparison_synthesis


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _has_envs(*names: str) -> bool:
    return all(bool(os.environ.get(name, "").strip()) for name in names)


HOSTED_PROVIDER_SPECS = [
    {
        "name": "openai",
        "provider": "openai",
        "module": "langchain_openai",
        "api_field": "openai_api_key",
        "api_env": "OPENAI_API_KEY",
        "discovery_env": "OPENAI_SMOKE_DISCOVERY_MODEL",
        "analysis_env": "OPENAI_SMOKE_ANALYSIS_MODEL",
        "compare_env": "OPENAI_SMOKE_COMPARE_MODEL",
    },
    {
        "name": "anthropic",
        "provider": "anthropic",
        "module": "langchain_anthropic",
        "api_field": "anthropic_api_key",
        "api_env": "ANTHROPIC_API_KEY",
        "discovery_env": "ANTHROPIC_SMOKE_DISCOVERY_MODEL",
        "analysis_env": "ANTHROPIC_SMOKE_ANALYSIS_MODEL",
        "compare_env": "ANTHROPIC_SMOKE_COMPARE_MODEL",
    },
    {
        "name": "gemini",
        "provider": "gemini",
        "module": "langchain_google_genai",
        "api_field": "google_api_key",
        "api_env": "GOOGLE_API_KEY",
        "discovery_env": "GEMINI_SMOKE_DISCOVERY_MODEL",
        "analysis_env": "GEMINI_SMOKE_ANALYSIS_MODEL",
        "compare_env": "GEMINI_SMOKE_COMPARE_MODEL",
    },
    {
        "name": "openai_compatible",
        "provider": "openai_compatible",
        "module": "langchain_openai",
        "api_field": "openai_compatible_api_key",
        "api_env": "OPENAI_COMPATIBLE_API_KEY",
        "base_url_field": "openai_compatible_base_url",
        "base_url_env": "OPENAI_COMPATIBLE_BASE_URL",
        "discovery_env": "OPENAI_COMPATIBLE_SMOKE_DISCOVERY_MODEL",
        "analysis_env": "OPENAI_COMPATIBLE_SMOKE_ANALYSIS_MODEL",
        "compare_env": "OPENAI_COMPATIBLE_SMOKE_COMPARE_MODEL",
    },
]

WORKFLOW_MODEL_SETTINGS = {
    "discovery": "discovery_query_model",
    "analysis": "analysis_model",
    "compare": "compare_synthesis_model",
}

LOCAL_EMBEDDINGS_READY = (
    _has_module("langchain_huggingface")
    and _has_module("sentence_transformers")
    and _has_envs("LOCAL_EMBEDDING_SMOKE_MODEL")
)

OLLAMA_READY = _has_module("langchain_ollama") and _has_envs(
    "OLLAMA_BASE_URL",
    "OLLAMA_SMOKE_CHAT_MODEL",
    "OLLAMA_SMOKE_STRUCTURED_MODEL",
)


def _is_hosted_provider_ready(spec: dict) -> bool:
    env_names = [
        spec["api_env"],
        spec["discovery_env"],
        spec["analysis_env"],
        spec["compare_env"],
    ]
    if spec.get("base_url_env"):
        env_names.append(spec["base_url_env"])
    return _has_module(spec["module"]) and _has_envs(*env_names)


def _get_ready_hosted_provider_specs() -> list[dict]:
    return [spec for spec in HOSTED_PROVIDER_SPECS if _is_hosted_provider_ready(spec)]


@contextmanager
def _patch_hosted_provider(spec: dict, workflow: str):
    model_setting = WORKFLOW_MODEL_SETTINGS[workflow]
    model_env = spec[f"{workflow}_env"]

    with ExitStack() as stack:
        stack.enter_context(patch.object(settings, "llm_provider", spec["provider"]))
        stack.enter_context(
            patch.object(
                settings,
                spec["api_field"],
                os.environ[spec["api_env"]],
            )
        )
        stack.enter_context(
            patch.object(
                settings,
                model_setting,
                os.environ[model_env],
            )
        )
        if spec.get("base_url_field"):
            stack.enter_context(
                patch.object(
                    settings,
                    spec["base_url_field"],
                    os.environ[spec["base_url_env"]],
                )
            )
        yield


class CacheResetMixin:
    def tearDown(self):
        get_chat_client.cache_clear()
        get_structured_client.cache_clear()
        get_embedding_client.cache_clear()


class HostedProviderLiveSmokeTests(CacheResetMixin, unittest.IsolatedAsyncioTestCase):
    async def test_discovery_query_generation_matrix(self):
        ready_specs = _get_ready_hosted_provider_specs()
        if not ready_specs:
            self.skipTest("Hosted provider live smoke env or dependency missing")

        for spec in ready_specs:
            with self.subTest(provider=spec["name"]):
                with _patch_hosted_provider(spec, "discovery"):
                    queries = await generate_search_queries(
                        "How can sparse attention improve long-context language models?",
                        max_queries=2,
                    )

                self.assertEqual(len(queries), 2)
                self.assertTrue(
                    all(isinstance(query, str) and query.strip() for query in queries)
                )

    async def test_analysis_generation_matrix(self):
        ready_specs = _get_ready_hosted_provider_specs()
        if not ready_specs:
            self.skipTest("Hosted provider live smoke env or dependency missing")

        for spec in ready_specs:
            with self.subTest(provider=spec["name"]):
                with _patch_hosted_provider(spec, "analysis"):
                    breakdown = analyze_paper(
                        title="Sparse Attention for Long Context",
                        abstract="The paper studies sparse attention for efficient long-context reasoning.",
                        sections=[
                            {
                                "title": "Method",
                                "content": "We introduce a sparse attention pattern that reduces quadratic cost while preserving quality.",
                            },
                            {
                                "title": "Results",
                                "content": "The method improves long-context benchmark accuracy while reducing memory usage.",
                            },
                        ],
                    )

                self.assertIn("problem", breakdown)
                self.assertIn("method", breakdown)

    async def test_compare_synthesis_generation_matrix(self):
        ready_specs = _get_ready_hosted_provider_specs()
        if not ready_specs:
            self.skipTest("Hosted provider live smoke env or dependency missing")

        for spec in ready_specs:
            with self.subTest(provider=spec["name"]):
                with _patch_hosted_provider(spec, "compare"):
                    synthesis = generate_comparison_synthesis(
                        [
                            {
                                "title": "Paper One",
                                "problem": "Long-context reasoning",
                                "method": "Sparse attention",
                                "dataset_or_eval_setup": "Needle-in-a-haystack",
                                "key_results": "Improved retrieval accuracy",
                                "strengths": "Efficient context handling",
                                "weaknesses": "More complex implementation",
                                "evidence_notes": {
                                    "problem": [],
                                    "method": [],
                                    "dataset_or_eval_setup": [],
                                    "key_results": [],
                                    "strengths": [],
                                    "weaknesses": [],
                                },
                                "warnings": [],
                            },
                            {
                                "title": "Paper Two",
                                "problem": "Long-context reasoning",
                                "method": "State-space model",
                                "dataset_or_eval_setup": "LongBench",
                                "key_results": "Lower latency at similar quality",
                                "strengths": "Fast inference",
                                "weaknesses": "Weaker very-long-context recall",
                                "evidence_notes": {
                                    "problem": [],
                                    "method": [],
                                    "dataset_or_eval_setup": [],
                                    "key_results": [],
                                    "strengths": [],
                                    "weaknesses": [],
                                },
                                "warnings": [],
                            },
                        ]
                    )

                self.assertIn("problem_landscape", synthesis)
                self.assertIn("method_divergence", synthesis)


@unittest.skipUnless(
    LOCAL_EMBEDDINGS_READY,
    "Local embedding live smoke env or dependency missing",
)
class LocalEmbeddingLiveSmokeTests(CacheResetMixin, unittest.TestCase):
    def test_sentence_transformer_query_embedding_generation(self):
        with patch.object(settings, "embedding_provider", "sentence_transformers"), patch.object(
            settings,
            "embedding_model",
            os.environ["LOCAL_EMBEDDING_SMOKE_MODEL"],
        ), patch.object(
            settings,
            "local_embedding_device",
            os.environ.get("LOCAL_EMBEDDING_DEVICE", ""),
        ):
            embedding = generate_query_embedding(
                "How can sparse attention improve long-context language models?"
            )

        self.assertTrue(isinstance(embedding, list))
        self.assertGreater(len(embedding), 0)


@unittest.skipUnless(OLLAMA_READY, "Ollama live smoke env or dependency missing")
class OllamaLiveSmokeTests(CacheResetMixin, unittest.TestCase):
    def test_ollama_chat_generation(self):
        with patch.object(settings, "llm_provider", "ollama"), patch.object(
            settings,
            "ollama_base_url",
            os.environ["OLLAMA_BASE_URL"],
        ), patch.object(
            settings,
            "llm_model",
            os.environ["OLLAMA_SMOKE_CHAT_MODEL"],
        ):
            result = get_chat_client().generate(
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with a short sentence about sparse attention.",
                    }
                ],
                temperature=0.0,
            )

        self.assertTrue(isinstance(result, str) and result.strip())

    def test_ollama_structured_generation(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "answer": {"type": "string"},
            },
            "required": ["answer"],
        }

        with patch.object(settings, "llm_provider", "ollama"), patch.object(
            settings,
            "ollama_base_url",
            os.environ["OLLAMA_BASE_URL"],
        ), patch.object(
            settings,
            "llm_model",
            os.environ["OLLAMA_SMOKE_STRUCTURED_MODEL"],
        ):
            result = get_structured_client().generate_structured(
                messages=[
                    {
                        "role": "user",
                        "content": "Return a JSON object with an answer about sparse attention.",
                    }
                ],
                schema_name="ollama_smoke_response",
                schema=schema,
                temperature=0.0,
            )

        self.assertIn("answer", result)
        self.assertTrue(result["answer"].strip())


if __name__ == "__main__":
    unittest.main()
