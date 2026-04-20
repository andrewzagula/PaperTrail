import unittest
from unittest.mock import patch

from app.llm.errors import ProviderRequestError
from app.llm.providers.anthropic import AnthropicChatClient, AnthropicStructuredClient
from app.llm.providers.gemini import GeminiChatClient, GeminiStructuredClient
from app.llm.providers.local_embeddings import SentenceTransformerEmbeddingClient
from app.llm.providers.ollama import OllamaChatClient, OllamaStructuredClient
from app.llm.providers.openai_compatible import (
    OpenAICompatibleChatClient,
    OpenAICompatibleStructuredClient,
)


TEST_MESSAGES = [{"role": "user", "content": "Return a value"}]
TEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "value": {"type": "string"},
    },
    "required": ["value"],
}


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeStructuredRunnable:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def invoke(self, messages):
        if self.error:
            raise self.error
        return self.payload


def make_fake_chat_model_class(
    *,
    text_responses=None,
    text_error=None,
    structured_payload=None,
    structured_error=None,
    recorder=None,
):
    class FakeChatModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.recorder = recorder

        def invoke(self, messages):
            if self.recorder is not None:
                self.recorder.append(("invoke", self.kwargs, messages))
            if text_error:
                raise text_error
            if not text_responses:
                return FakeResponse("")
            return FakeResponse(text_responses.pop(0))

        def with_structured_output(self, schema=None, **kwargs):
            if self.recorder is not None:
                self.recorder.append(("structured", self.kwargs, schema, kwargs))
            return FakeStructuredRunnable(
                payload=structured_payload,
                error=structured_error,
            )

    return FakeChatModel


def make_fake_embedding_model_class(
    *,
    query_vector=None,
    document_vectors=None,
    error=None,
    recorder=None,
):
    class FakeEmbeddingModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.recorder = recorder

        def embed_documents(self, texts):
            if self.recorder is not None:
                self.recorder.append(("embed_documents", self.kwargs, texts))
            if error:
                raise error
            return document_vectors or [[0.1, 0.2] for _ in texts]

        def embed_query(self, text):
            if self.recorder is not None:
                self.recorder.append(("embed_query", self.kwargs, text))
            if error:
                raise error
            return query_vector or [0.3, 0.4]

    return FakeEmbeddingModel


class AnthropicProviderTests(unittest.TestCase):
    def test_anthropic_chat_generation_returns_text(self):
        recorder = []
        client = AnthropicChatClient(api_key="key", default_model="claude-test")
        fake_class = make_fake_chat_model_class(
            text_responses=["hello from anthropic"],
            recorder=recorder,
        )

        with patch(
            "app.llm.providers.anthropic._load_chat_anthropic_class",
            return_value=fake_class,
        ):
            result = client.generate(TEST_MESSAGES, temperature=0.4)

        self.assertEqual(result, "hello from anthropic")
        self.assertEqual(recorder[0][0], "invoke")
        self.assertEqual(recorder[0][1]["model"], "claude-test")
        self.assertEqual(recorder[0][1]["temperature"], 0.4)

    def test_anthropic_structured_generation_uses_native_payload(self):
        client = AnthropicStructuredClient(api_key="key", default_model="claude-test")
        fake_class = make_fake_chat_model_class(
            structured_payload={"value": "native"},
        )

        with patch(
            "app.llm.providers.anthropic._load_chat_anthropic_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "native"})

    def test_anthropic_structured_generation_falls_back_to_json(self):
        client = AnthropicStructuredClient(api_key="key", default_model="claude-test")
        fake_class = make_fake_chat_model_class(
            structured_error=RuntimeError("native unavailable"),
            text_responses=['{"value": "fallback"}'],
        )

        with patch(
            "app.llm.providers.anthropic._load_chat_anthropic_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "fallback"})

    def test_anthropic_structured_generation_repairs_once(self):
        client = AnthropicStructuredClient(api_key="key", default_model="claude-test")
        fake_class = make_fake_chat_model_class(
            structured_error=RuntimeError("native unavailable"),
            text_responses=['{"wrong": "shape"}', '{"value": "repaired"}'],
        )

        with patch(
            "app.llm.providers.anthropic._load_chat_anthropic_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "repaired"})

    def test_anthropic_wraps_provider_failures(self):
        client = AnthropicChatClient(api_key="key", default_model="claude-test")
        fake_class = make_fake_chat_model_class(
            text_error=RuntimeError("provider boom"),
        )

        with patch(
            "app.llm.providers.anthropic._load_chat_anthropic_class",
            return_value=fake_class,
        ):
            with self.assertRaises(ProviderRequestError):
                client.generate(TEST_MESSAGES)


class GeminiProviderTests(unittest.TestCase):
    def test_gemini_chat_generation_returns_text(self):
        recorder = []
        client = GeminiChatClient(api_key="key", default_model="gemini-test")
        fake_class = make_fake_chat_model_class(
            text_responses=["hello from gemini"],
            recorder=recorder,
        )

        with patch(
            "app.llm.providers.gemini._load_chat_google_generative_ai_class",
            return_value=fake_class,
        ):
            result = client.generate(TEST_MESSAGES, temperature=0.1)

        self.assertEqual(result, "hello from gemini")
        self.assertEqual(recorder[0][1]["model"], "gemini-test")
        self.assertEqual(recorder[0][1]["temperature"], 0.1)

    def test_gemini_structured_generation_uses_native_payload(self):
        client = GeminiStructuredClient(api_key="key", default_model="gemini-test")
        fake_class = make_fake_chat_model_class(
            structured_payload={"value": "native"},
        )

        with patch(
            "app.llm.providers.gemini._load_chat_google_generative_ai_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "native"})

    def test_gemini_structured_generation_falls_back_to_json(self):
        client = GeminiStructuredClient(api_key="key", default_model="gemini-test")
        fake_class = make_fake_chat_model_class(
            structured_error=RuntimeError("native unavailable"),
            text_responses=['{"value": "fallback"}'],
        )

        with patch(
            "app.llm.providers.gemini._load_chat_google_generative_ai_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "fallback"})

    def test_gemini_structured_generation_repairs_once(self):
        client = GeminiStructuredClient(api_key="key", default_model="gemini-test")
        fake_class = make_fake_chat_model_class(
            structured_error=RuntimeError("native unavailable"),
            text_responses=['{"wrong": "shape"}', '{"value": "repaired"}'],
        )

        with patch(
            "app.llm.providers.gemini._load_chat_google_generative_ai_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "repaired"})

    def test_gemini_wraps_provider_failures(self):
        client = GeminiStructuredClient(api_key="key", default_model="gemini-test")
        fake_class = make_fake_chat_model_class(
            structured_error=RuntimeError("provider boom"),
            text_error=RuntimeError("provider boom"),
        )

        with patch(
            "app.llm.providers.gemini._load_chat_google_generative_ai_class",
            return_value=fake_class,
        ):
            with self.assertRaises(ProviderRequestError):
                client.generate_structured(
                    TEST_MESSAGES,
                    schema_name="test_schema",
                    schema=TEST_SCHEMA,
                )


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_openai_compatible_chat_generation_returns_text_and_base_url(self):
        recorder = []
        client = OpenAICompatibleChatClient(
            api_key="key",
            base_url="https://compatible.example/v1",
            default_model="compatible-test",
        )
        fake_class = make_fake_chat_model_class(
            text_responses=["hello from compatible"],
            recorder=recorder,
        )

        with patch(
            "app.llm.providers.openai_compatible._load_chat_openai_class",
            return_value=fake_class,
        ):
            result = client.generate(TEST_MESSAGES, temperature=0.25)

        self.assertEqual(result, "hello from compatible")
        self.assertEqual(recorder[0][1]["model_name"], "compatible-test")
        self.assertEqual(recorder[0][1]["openai_api_base"], "https://compatible.example/v1")
        self.assertEqual(recorder[0][1]["openai_api_key"], "key")

    def test_openai_compatible_structured_generation_uses_native_payload(self):
        client = OpenAICompatibleStructuredClient(
            api_key="key",
            base_url="https://compatible.example/v1",
            default_model="compatible-test",
        )
        fake_class = make_fake_chat_model_class(
            structured_payload={"value": "native"},
        )

        with patch(
            "app.llm.providers.openai_compatible._load_chat_openai_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "native"})

    def test_openai_compatible_structured_generation_falls_back_to_json(self):
        client = OpenAICompatibleStructuredClient(
            api_key="key",
            base_url="https://compatible.example/v1",
            default_model="compatible-test",
        )
        fake_class = make_fake_chat_model_class(
            structured_error=RuntimeError("native unavailable"),
            text_responses=['{"value": "fallback"}'],
        )

        with patch(
            "app.llm.providers.openai_compatible._load_chat_openai_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "fallback"})

    def test_openai_compatible_wraps_provider_failures(self):
        client = OpenAICompatibleChatClient(
            api_key="key",
            base_url="https://compatible.example/v1",
            default_model="compatible-test",
        )
        fake_class = make_fake_chat_model_class(
            text_error=RuntimeError("provider boom"),
        )

        with patch(
            "app.llm.providers.openai_compatible._load_chat_openai_class",
            return_value=fake_class,
        ):
            with self.assertRaises(ProviderRequestError):
                client.generate(TEST_MESSAGES)


class OllamaProviderTests(unittest.TestCase):
    def test_ollama_chat_generation_returns_text(self):
        recorder = []
        client = OllamaChatClient(
            base_url="http://localhost:11434",
            default_model="llama3.1:8b",
        )
        fake_class = make_fake_chat_model_class(
            text_responses=["hello from ollama"],
            recorder=recorder,
        )

        with patch(
            "app.llm.providers.ollama._load_chat_ollama_class",
            return_value=fake_class,
        ):
            result = client.generate(TEST_MESSAGES, temperature=0.15)

        self.assertEqual(result, "hello from ollama")
        self.assertEqual(recorder[0][1]["model"], "llama3.1:8b")
        self.assertEqual(recorder[0][1]["base_url"], "http://localhost:11434")

    def test_ollama_structured_generation_falls_back_to_json(self):
        client = OllamaStructuredClient(
            base_url="http://localhost:11434",
            default_model="llama3.1:8b",
        )
        fake_class = make_fake_chat_model_class(
            text_responses=['{"value": "fallback"}'],
        )

        with patch(
            "app.llm.providers.ollama._load_chat_ollama_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "fallback"})

    def test_ollama_structured_generation_repairs_once(self):
        client = OllamaStructuredClient(
            base_url="http://localhost:11434",
            default_model="llama3.1:8b",
        )
        fake_class = make_fake_chat_model_class(
            text_responses=['{"wrong": "shape"}', '{"value": "repaired"}'],
        )

        with patch(
            "app.llm.providers.ollama._load_chat_ollama_class",
            return_value=fake_class,
        ):
            result = client.generate_structured(
                TEST_MESSAGES,
                schema_name="test_schema",
                schema=TEST_SCHEMA,
            )

        self.assertEqual(result, {"value": "repaired"})

    def test_ollama_wraps_provider_failures(self):
        client = OllamaChatClient(
            base_url="http://localhost:11434",
            default_model="llama3.1:8b",
        )
        fake_class = make_fake_chat_model_class(
            text_error=RuntimeError("provider boom"),
        )

        with patch(
            "app.llm.providers.ollama._load_chat_ollama_class",
            return_value=fake_class,
        ):
            with self.assertRaises(ProviderRequestError):
                client.generate(TEST_MESSAGES)


class LocalEmbeddingProviderTests(unittest.TestCase):
    def test_sentence_transformer_embeddings_use_device_when_configured(self):
        recorder = []
        client = SentenceTransformerEmbeddingClient(
            default_model="sentence-transformers/all-MiniLM-L6-v2",
            device="cpu",
        )
        fake_class = make_fake_embedding_model_class(
            recorder=recorder,
            document_vectors=[[0.1, 0.2]],
            query_vector=[0.3, 0.4],
        )

        with patch(
            "app.llm.providers.local_embeddings._load_huggingface_embeddings_class",
            return_value=fake_class,
        ):
            documents = client.embed_texts(["hello"])
            query = client.embed_query("question")

        self.assertEqual(documents, [[0.1, 0.2]])
        self.assertEqual(query, [0.3, 0.4])
        self.assertEqual(
            recorder[0][1]["model_kwargs"],
            {"device": "cpu"},
        )
        self.assertEqual(
            recorder[0][1]["model_name"],
            "sentence-transformers/all-MiniLM-L6-v2",
        )

    def test_sentence_transformer_embeddings_wrap_runtime_failures(self):
        client = SentenceTransformerEmbeddingClient(
            default_model="sentence-transformers/all-MiniLM-L6-v2",
        )
        fake_class = make_fake_embedding_model_class(error=RuntimeError("embed boom"))

        with patch(
            "app.llm.providers.local_embeddings._load_huggingface_embeddings_class",
            return_value=fake_class,
        ):
            with self.assertRaises(ProviderRequestError):
                client.embed_query("question")


if __name__ == "__main__":
    unittest.main()
