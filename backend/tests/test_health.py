import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _collect_keys(payload):
    if isinstance(payload, dict):
        keys = set(payload.keys())
        for value in payload.values():
            keys.update(_collect_keys(value))
        return keys
    if isinstance(payload, list):
        keys = set()
        for value in payload:
            keys.update(_collect_keys(value))
        return keys
    return set()


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.init_db_patch = patch("app.main.init_db", return_value=None)
        self.init_db_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.init_db_patch.stop()

    def test_health_remains_backward_compatible(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "papertrail-api"},
        )

    def test_health_details_reports_paths_and_config_without_secret_values(self):
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings,
            "llm_model",
            "gpt-test",
        ), patch.object(settings, "embedding_provider", "sentence_transformers"), patch.object(
            settings,
            "embedding_model",
            "embedding-test",
        ), patch.object(
            settings,
            "openai_api_key",
            "super-secret-openai-key",
        ):
            response = self.client.get("/health/details")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "papertrail-api")
        self.assertEqual(payload["llm"]["provider"], "openai")
        self.assertEqual(payload["llm"]["model"], "gpt-test")
        self.assertTrue(payload["llm"]["configured"])
        self.assertEqual(payload["llm"]["missing_settings"], [])
        self.assertEqual(payload["embedding"]["provider"], "sentence_transformers")
        self.assertEqual(payload["embedding"]["model"], "embedding-test")
        self.assertTrue(payload["embedding"]["configured"])
        self.assertIn("data_dir", payload["paths"])
        self.assertIn("database_path", payload["paths"])
        self.assertIn("chroma_dir", payload["paths"])
        self.assertNotIn("super-secret-openai-key", json.dumps(payload))
        self.assertNotIn("api_key", {key.lower() for key in _collect_keys(payload)})

    def test_health_details_marks_missing_provider_config_degraded(self):
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings,
            "embedding_provider",
            "openai",
        ), patch.object(settings, "openai_api_key", ""):
            response = self.client.get("/health/details")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["llm"]["configured"])
        self.assertFalse(payload["embedding"]["configured"])
        self.assertEqual(payload["llm"]["missing_settings"], ["OPENAI_API_KEY"])
        self.assertEqual(payload["embedding"]["missing_settings"], ["OPENAI_API_KEY"])


if __name__ == "__main__":
    unittest.main()
