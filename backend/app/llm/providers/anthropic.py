from __future__ import annotations

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


def _load_chat_anthropic_class():
    module = load_provider_dependency("langchain_anthropic", "langchain-anthropic")
    return module.ChatAnthropic


class AnthropicChatClient:
    def __init__(self, *, api_key: str, default_model: str):
        self.api_key = api_key
        self.default_model = default_model

    def _build_model(
        self,
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> BaseChatModel:
        chat_anthropic = _load_chat_anthropic_class()
        return chat_anthropic(
            model=model or self.default_model,
            temperature=temperature,
            anthropic_api_key=self.api_key or None,
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
            raise_provider_request_error("Anthropic", "chat generation", error)

        return content_to_text(response.content).strip()


class AnthropicStructuredClient(AnthropicChatClient):
    def _generate_native_structured(
        self,
        messages: list[LLMMessage],
        *,
        schema: dict,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict:
        try:
            payload = self._build_model(
                model=model,
                temperature=temperature,
            ).with_structured_output(schema=schema).invoke(to_langchain_messages(messages))
        except Exception as error:
            raise_provider_request_error("Anthropic", "structured generation", error)

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
