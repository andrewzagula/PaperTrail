import unittest
from unittest.mock import patch

from app.config import settings
from app.llm.errors import InvalidProviderConfigError, MissingProviderCredentialsError
from app.llm.factory import (
    UnsupportedProviderError,
    get_chat_client,
    get_embedding_client,
    get_structured_client,
)
from app.llm.providers.anthropic import AnthropicChatClient, AnthropicStructuredClient
from app.llm.providers.gemini import GeminiChatClient, GeminiStructuredClient
from app.llm.providers.local_embeddings import SentenceTransformerEmbeddingClient
from app.llm.providers.openai import (
    OpenAIChatClient,
    OpenAIEmbeddingClient,
    OpenAIStructuredClient,
)
from app.llm.providers.ollama import OllamaChatClient, OllamaStructuredClient
from app.llm.providers.openai_compatible import (
    OpenAICompatibleChatClient,
    OpenAICompatibleStructuredClient,
)


class LLMFactoryTests(unittest.TestCase):
    def setUp(self):
        get_chat_client.cache_clear()
        get_structured_client.cache_clear()
        get_embedding_client.cache_clear()

    def tearDown(self):
        get_chat_client.cache_clear()
        get_structured_client.cache_clear()
        get_embedding_client.cache_clear()

    def test_factory_returns_openai_clients_by_default(self):
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings,
            "embedding_provider",
            "openai",
        ), patch.object(settings, "openai_api_key", "test-openai-key"):
            self.assertIsInstance(get_chat_client(), OpenAIChatClient)
            self.assertIsInstance(get_structured_client(), OpenAIStructuredClient)
            self.assertIsInstance(get_embedding_client(), OpenAIEmbeddingClient)

    def test_factory_returns_anthropic_clients(self):
        with patch.object(settings, "llm_provider", "anthropic"), patch.object(
            settings,
            "anthropic_api_key",
            "test-anthropic-key",
        ):
            self.assertIsInstance(get_chat_client(), AnthropicChatClient)
            self.assertIsInstance(get_structured_client(), AnthropicStructuredClient)

    def test_factory_returns_gemini_clients(self):
        with patch.object(settings, "llm_provider", "gemini"), patch.object(
            settings,
            "google_api_key",
            "test-google-key",
        ):
            self.assertIsInstance(get_chat_client(), GeminiChatClient)
            self.assertIsInstance(get_structured_client(), GeminiStructuredClient)

    def test_factory_returns_openai_compatible_clients(self):
        with patch.object(settings, "llm_provider", "openai_compatible"), patch.object(
            settings,
            "openai_compatible_api_key",
            "test-compatible-key",
        ), patch.object(
            settings,
            "openai_compatible_base_url",
            "https://compatible.example/v1",
        ):
            self.assertIsInstance(get_chat_client(), OpenAICompatibleChatClient)
            self.assertIsInstance(get_structured_client(), OpenAICompatibleStructuredClient)

    def test_factory_returns_ollama_clients(self):
        with patch.object(settings, "llm_provider", "ollama"), patch.object(
            settings,
            "ollama_base_url",
            "http://ollama.local:11434",
        ):
            self.assertIsInstance(get_chat_client(), OllamaChatClient)
            self.assertIsInstance(get_structured_client(), OllamaStructuredClient)

    def test_factory_uses_updated_settings_after_cache_clear(self):
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings,
            "embedding_provider",
            "openai",
        ), patch.object(settings, "openai_api_key", "test-openai-key"), patch.object(
            settings,
            "llm_model",
            "gpt-test",
        ), patch.object(settings, "openai_base_url", "https://example.test/v1"):
            chat_client = get_chat_client()
            structured_client = get_structured_client()
            with patch.object(settings, "embedding_model", "embedding-test"):
                get_embedding_client.cache_clear()
                embedding_client = get_embedding_client()

        self.assertEqual(chat_client.default_model, "gpt-test")
        self.assertEqual(structured_client.default_model, "gpt-test")
        self.assertEqual(embedding_client.default_model, "embedding-test")
        self.assertEqual(chat_client.base_url, "https://example.test/v1")
        self.assertEqual(embedding_client.base_url, "https://example.test/v1")

    def test_factory_supports_mixed_llm_and_embedding_providers(self):
        with patch.object(settings, "llm_provider", "anthropic"), patch.object(
            settings,
            "anthropic_api_key",
            "test-anthropic-key",
        ), patch.object(settings, "embedding_provider", "sentence_transformers"), patch.object(
            settings,
            "embedding_model",
            "sentence-transformers/all-MiniLM-L6-v2",
        ):
            self.assertIsInstance(get_chat_client(), AnthropicChatClient)
            self.assertIsInstance(get_structured_client(), AnthropicStructuredClient)
            self.assertIsInstance(get_embedding_client(), SentenceTransformerEmbeddingClient)

    def test_factory_rejects_unsupported_providers(self):
        with patch.object(settings, "llm_provider", "unknown-provider"):
            with self.assertRaises(UnsupportedProviderError):
                get_chat_client()

        get_chat_client.cache_clear()

        with patch.object(settings, "embedding_provider", "local"):
            with self.assertRaises(UnsupportedProviderError):
                get_embedding_client()

    def test_factory_rejects_missing_provider_credentials(self):
        with patch.object(settings, "llm_provider", "openai"), patch.object(
            settings,
            "openai_api_key",
            "",
        ):
            with self.assertRaises(MissingProviderCredentialsError):
                get_chat_client()

        get_chat_client.cache_clear()

        with patch.object(settings, "llm_provider", "anthropic"), patch.object(
            settings,
            "anthropic_api_key",
            "",
        ):
            with self.assertRaises(MissingProviderCredentialsError):
                get_structured_client()

        get_structured_client.cache_clear()

        with patch.object(settings, "embedding_provider", "openai"), patch.object(
            settings,
            "openai_api_key",
            "",
        ):
            with self.assertRaises(MissingProviderCredentialsError):
                get_embedding_client()

        get_chat_client.cache_clear()

        with patch.object(settings, "llm_provider", "openai_compatible"), patch.object(
            settings,
            "openai_compatible_api_key",
            "",
        ), patch.object(
            settings,
            "openai_compatible_base_url",
            "https://compatible.example/v1",
        ):
            with self.assertRaises(MissingProviderCredentialsError):
                get_chat_client()

    def test_factory_rejects_missing_openai_compatible_base_url(self):
        with patch.object(settings, "llm_provider", "openai_compatible"), patch.object(
            settings,
            "openai_compatible_api_key",
            "test-compatible-key",
        ), patch.object(settings, "openai_compatible_base_url", ""):
            with self.assertRaises(InvalidProviderConfigError):
                get_chat_client()


if __name__ == "__main__":
    unittest.main()
