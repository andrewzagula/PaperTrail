import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.diagnostics import _looks_like_placeholder
from app.main import app

PLACEHOLDER_KEY = "sk-your-openai-api-key-here"
REAL_LOOKING_KEY = "sk-proj-9f2ba71c4d8e5a6b3c0d1e2f3a4b5c6d"


class PlaceholderDetectionTests(unittest.TestCase):
    def test_detects_the_shipped_env_example_placeholder(self):
        self.assertTrue(_looks_like_placeholder(PLACEHOLDER_KEY))

    def test_detects_common_placeholder_shapes(self):
        for value in (
            "changeme",
            "replace-me",
            "<your key>",
            "xxxxxxxx",
            "PLACEHOLDER",
        ):
            self.assertTrue(_looks_like_placeholder(value), value)

    def test_does_not_flag_real_looking_keys(self):
        self.assertFalse(_looks_like_placeholder(REAL_LOOKING_KEY))
        self.assertFalse(_looks_like_placeholder("sk-ant-api03-abc123def456"))

    def test_empty_is_not_a_placeholder(self):
        """Empty is already reported as missing; do not double-report it."""
        self.assertFalse(_looks_like_placeholder(""))
        self.assertFalse(_looks_like_placeholder("   "))


class HealthDetailsPlaceholderTests(unittest.TestCase):
    def setUp(self):
        self.init_db_patch = patch("app.main.init_db", return_value=None)
        self.init_db_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.init_db_patch.stop()

    def test_placeholder_key_is_reported_degraded(self):
        """The original bug: an unedited .env reported a fully healthy service."""
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings, "embedding_provider", "openai"
        ), patch.object(settings, "openai_api_key", PLACEHOLDER_KEY):
            payload = self.client.get("/health/details").json()

        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["llm"]["configured"])
        self.assertEqual(
            payload["llm"]["placeholder_settings"], ["OPENAI_API_KEY"]
        )
        self.assertEqual(payload["llm"]["missing_settings"], [])

    def test_real_looking_key_is_reported_configured(self):
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings, "embedding_provider", "openai"
        ), patch.object(settings, "openai_api_key", REAL_LOOKING_KEY):
            payload = self.client.get("/health/details").json()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["llm"]["configured"])
        self.assertEqual(payload["llm"]["placeholder_settings"], [])

    def test_configured_does_not_claim_credentials_are_verified(self):
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings, "embedding_provider", "openai"
        ), patch.object(settings, "openai_api_key", REAL_LOOKING_KEY):
            payload = self.client.get("/health/details").json()

        self.assertTrue(payload["llm"]["configured"])
        self.assertFalse(payload["credentials_verified"])
        self.assertEqual(
            payload["llm"]["credential_check"]["status"], "not_checked"
        )


class HealthDetailsProbeTests(unittest.TestCase):
    def setUp(self):
        self.init_db_patch = patch("app.main.init_db", return_value=None)
        self.init_db_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.init_db_patch.stop()

    def _get(self, probe: bool):
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings, "embedding_provider", "openai"
        ), patch.object(settings, "openai_api_key", REAL_LOOKING_KEY):
            suffix = "?probe=true" if probe else ""
            return self.client.get(f"/health/details{suffix}").json()

    def test_no_provider_call_without_probe(self):
        with patch("app.llm.get_chat_client") as chat:
            payload = self._get(probe=False)
        chat.assert_not_called()
        self.assertEqual(
            payload["llm"]["credential_check"]["status"], "not_checked"
        )

    def test_successful_probe_marks_credentials_verified(self):
        with patch("app.diagnostics._probe_llm", return_value={
            "status": "ok", "detail": "Provider accepted a test request."
        }), patch("app.diagnostics._probe_embedding", return_value={
            "status": "ok", "detail": "Provider accepted a test request."
        }):
            payload = self._get(probe=True)

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["credentials_verified"])
        self.assertEqual(payload["llm"]["credential_check"]["status"], "ok")

    def test_failed_probe_marks_service_degraded(self):
        """A well-formed but rejected key must not report a healthy service."""
        def boom():
            raise RuntimeError("Incorrect API key provided")

        with patch("app.diagnostics._probe_llm", side_effect=boom), patch(
            "app.diagnostics._probe_embedding", side_effect=boom
        ):
            payload = self._get(probe=True)

        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["credentials_verified"])
        self.assertEqual(payload["llm"]["credential_check"]["status"], "failed")
        self.assertIn("Incorrect API key", payload["llm"]["credential_check"]["detail"])

    def test_probe_is_skipped_when_settings_are_incomplete(self):
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings, "embedding_provider", "openai"
        ), patch.object(settings, "openai_api_key", ""):
            with patch("app.diagnostics._probe_llm") as probe:
                payload = self.client.get("/health/details?probe=true").json()

        probe.assert_not_called()
        self.assertEqual(payload["llm"]["credential_check"]["status"], "skipped")

    def test_probe_failure_detail_never_echoes_the_key(self):
        def leak():
            raise RuntimeError(f"auth failed for {REAL_LOOKING_KEY}")

        with patch("app.diagnostics._probe_llm", side_effect=leak), patch(
            "app.diagnostics._probe_embedding", side_effect=leak
        ):
            payload = self._get(probe=True)

        self.assertNotIn(REAL_LOOKING_KEY, json.dumps(payload))
        self.assertIn("[redacted]", payload["llm"]["credential_check"]["detail"])


if __name__ == "__main__":
    unittest.main()
