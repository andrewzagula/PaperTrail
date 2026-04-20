from __future__ import annotations

from importlib import import_module
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.llm.base import LLMMessage
from app.llm.errors import LLMProviderError, MissingProviderDependencyError, ProviderRequestError


def load_provider_dependency(module_name: str, package_name: str) -> Any:
    try:
        return import_module(module_name)
    except ImportError as error:
        raise MissingProviderDependencyError(
            f"Missing optional dependency '{package_name}' required for provider support."
        ) from error


def to_langchain_messages(messages: list[LLMMessage]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []

    for message in messages:
        role = message["role"]
        content = message["content"]

        if role == "system":
            converted.append(SystemMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))

    return converted


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)

    return str(content or "")


def structured_payload_to_dict(payload: Any) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if isinstance(payload, dict):
        return payload
    return dict(payload)


def raise_provider_request_error(
    provider_name: str,
    operation: str,
    error: Exception,
) -> None:
    if isinstance(error, LLMProviderError):
        raise error

    raise ProviderRequestError(
        f"{provider_name} provider request failed during {operation}."
    ) from error
