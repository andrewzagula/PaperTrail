from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.llm.base import ChatModelClient, EmbeddingClient, StructuredModelClient
from app.llm.errors import (
    InvalidProviderConfigError,
    MissingProviderCredentialsError,
    UnsupportedProviderError,
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


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower()


def _require_setting(value: str, *, setting_name: str, provider_name: str) -> str:
    if value.strip():
        return value

    raise MissingProviderCredentialsError(
        f"Missing required setting '{setting_name}' for provider '{provider_name}'."
    )


def _require_config(value: str, *, setting_name: str, provider_name: str) -> str:
    if value.strip():
        return value

    raise InvalidProviderConfigError(
        f"Missing required setting '{setting_name}' for provider '{provider_name}'."
    )


@lru_cache(maxsize=1)
def get_chat_client() -> ChatModelClient:
    provider = _normalize_provider(settings.llm_provider)
    if provider == "openai":
        return OpenAIChatClient(
            api_key=_require_setting(
                settings.openai_api_key,
                setting_name="OPENAI_API_KEY",
                provider_name="openai",
            ),
            base_url=settings.openai_base_url,
            default_model=settings.llm_model,
        )

    if provider == "anthropic":
        return AnthropicChatClient(
            api_key=_require_setting(
                settings.anthropic_api_key,
                setting_name="ANTHROPIC_API_KEY",
                provider_name="anthropic",
            ),
            default_model=settings.llm_model,
        )

    if provider == "gemini":
        return GeminiChatClient(
            api_key=_require_setting(
                settings.google_api_key,
                setting_name="GOOGLE_API_KEY",
                provider_name="gemini",
            ),
            default_model=settings.llm_model,
        )

    if provider == "openai_compatible":
        return OpenAICompatibleChatClient(
            api_key=_require_setting(
                settings.openai_compatible_api_key,
                setting_name="OPENAI_COMPATIBLE_API_KEY",
                provider_name="openai_compatible",
            ),
            base_url=_require_config(
                settings.openai_compatible_base_url,
                setting_name="OPENAI_COMPATIBLE_BASE_URL",
                provider_name="openai_compatible",
            ),
            default_model=settings.llm_model,
        )

    if provider == "ollama":
        return OllamaChatClient(
            base_url=settings.ollama_base_url,
            default_model=settings.llm_model,
        )

    raise UnsupportedProviderError(f"Unsupported chat provider: {provider}")


@lru_cache(maxsize=1)
def get_structured_client() -> StructuredModelClient:
    provider = _normalize_provider(settings.llm_provider)
    if provider == "openai":
        return OpenAIStructuredClient(
            api_key=_require_setting(
                settings.openai_api_key,
                setting_name="OPENAI_API_KEY",
                provider_name="openai",
            ),
            base_url=settings.openai_base_url,
            default_model=settings.llm_model,
        )

    if provider == "anthropic":
        return AnthropicStructuredClient(
            api_key=_require_setting(
                settings.anthropic_api_key,
                setting_name="ANTHROPIC_API_KEY",
                provider_name="anthropic",
            ),
            default_model=settings.llm_model,
        )

    if provider == "gemini":
        return GeminiStructuredClient(
            api_key=_require_setting(
                settings.google_api_key,
                setting_name="GOOGLE_API_KEY",
                provider_name="gemini",
            ),
            default_model=settings.llm_model,
        )

    if provider == "openai_compatible":
        return OpenAICompatibleStructuredClient(
            api_key=_require_setting(
                settings.openai_compatible_api_key,
                setting_name="OPENAI_COMPATIBLE_API_KEY",
                provider_name="openai_compatible",
            ),
            base_url=_require_config(
                settings.openai_compatible_base_url,
                setting_name="OPENAI_COMPATIBLE_BASE_URL",
                provider_name="openai_compatible",
            ),
            default_model=settings.llm_model,
        )

    if provider == "ollama":
        return OllamaStructuredClient(
            base_url=settings.ollama_base_url,
            default_model=settings.llm_model,
        )

    raise UnsupportedProviderError(f"Unsupported structured provider: {provider}")


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    provider = _normalize_provider(settings.embedding_provider)
    if provider == "openai":
        return OpenAIEmbeddingClient(
            api_key=_require_setting(
                settings.openai_api_key,
                setting_name="OPENAI_API_KEY",
                provider_name="openai",
            ),
            base_url=settings.openai_base_url,
            default_model=settings.embedding_model,
        )

    if provider == "sentence_transformers":
        return SentenceTransformerEmbeddingClient(
            default_model=settings.embedding_model,
            device=settings.local_embedding_device,
        )

    raise UnsupportedProviderError(f"Unsupported embedding provider: {provider}")
