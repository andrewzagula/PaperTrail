from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.llm.base import LLMMessage
from app.llm.providers.common import content_to_text, load_provider_dependency, raise_provider_request_error, to_langchain_messages
from app.llm.structured import StructuredOutputError, generate_structured_payload


def _load_chat_ollama_class():
    module = load_provider_dependency("langchain_ollama", "langchain-ollama")
    return module.ChatOllama


class OllamaChatClient:
    def __init__(self, *, base_url: str, default_model: str):
        self.base_url = base_url
        self.default_model = default_model

    def _build_model(
        self,
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> BaseChatModel:
        chat_ollama = _load_chat_ollama_class()
        return chat_ollama(
            model=model or self.default_model,
            temperature=temperature,
            base_url=self.base_url or None,
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
            raise_provider_request_error("Ollama", "chat generation", error)

        return content_to_text(response.content).strip()


class OllamaStructuredClient(OllamaChatClient):
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
            native_generate=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                StructuredOutputError(
                    "Ollama native structured output is disabled; using JSON fallback."
                )
            ),
            text_generate=lambda request_messages, request_model, request_temperature: self.generate(
                request_messages,
                model=request_model,
                temperature=request_temperature,
            ),
        )
