from __future__ import annotations

from typing import Literal, Protocol, TypedDict


class LLMMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatModelClient(Protocol):
    def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        ...


class StructuredModelClient(Protocol):
    def generate_structured(
        self,
        messages: list[LLMMessage],
        *,
        schema_name: str,
        schema: dict,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict:
        ...


class EmbeddingClient(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...
