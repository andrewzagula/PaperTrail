from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from app.llm.base import LLMMessage
from app.llm.providers.common import (
    content_to_text,
    load_provider_dependency,
    raise_provider_request_error,
    structured_payload_to_dict,
    to_langchain_messages,
)
from app.llm.structured import generate_structured_payload


def _load_chat_openai_class():
    module = load_provider_dependency("langchain_openai", "langchain-openai")
    return module.ChatOpenAI


def _load_openai_embeddings_class():
    module = load_provider_dependency("langchain_openai", "langchain-openai")
    return module.OpenAIEmbeddings


class OpenAIChatClient:
    def __init__(self, *, api_key: str, base_url: str, default_model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model

    def _build_model(
        self,
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> BaseChatModel:
        chat_openai = _load_chat_openai_class()
        return chat_openai(
            model_name=model or self.default_model,
            temperature=temperature,
            openai_api_key=self.api_key or None,
            openai_api_base=self.base_url or None,
        )

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        try:
            response = self._build_model(model=model, temperature=temperature).invoke(
                to_langchain_messages(messages)
            )
        except Exception as error:
            raise_provider_request_error("OpenAI", "chat generation", error)

        return content_to_text(response.content).strip()


class OpenAIStructuredClient(OpenAIChatClient):
    def _generate_native_structured(
        self,
        messages: list[LLMMessage],
        *,
        schema: dict,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict:
        try:
            runnable = self._build_model(
                model=model,
                temperature=temperature,
            ).with_structured_output(
                schema=schema,
                method="json_schema",
                strict=True,
            )
            payload = runnable.invoke(to_langchain_messages(messages))
        except Exception as error:
            raise_provider_request_error("OpenAI", "structured generation", error)

        return structured_payload_to_dict(payload)

    def generate_structured(
        self,
        messages: list[LLMMessage],
        *,
        schema_name: str,
        schema: dict,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict:
        return generate_structured_payload(
            messages=messages,
            schema_name=schema_name,
            schema=schema,
            model=model,
            temperature=temperature,
            native_generate=lambda request_messages, request_model, request_temperature, request_schema: self._generate_native_structured(
                request_messages,
                schema=request_schema,
                model=request_model,
                temperature=request_temperature,
            ),
            text_generate=lambda request_messages, request_model, request_temperature: self.generate(
                request_messages,
                model=request_model,
                temperature=request_temperature,
            ),
        )


class OpenAIEmbeddingClient:
    def __init__(self, *, api_key: str, base_url: str, default_model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model

    def _build_model(self) -> Embeddings:
        openai_embeddings = _load_openai_embeddings_class()
        return openai_embeddings(
            model=self.default_model,
            openai_api_key=self.api_key or None,
            openai_api_base=self.base_url or None,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return self._build_model().embed_documents(texts)
        except Exception as error:
            raise_provider_request_error("OpenAI", "embedding generation", error)

    def embed_query(self, text: str) -> list[float]:
        try:
            return self._build_model().embed_query(text)
        except Exception as error:
            raise_provider_request_error("OpenAI", "query embedding generation", error)
