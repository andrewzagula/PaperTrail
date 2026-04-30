from __future__ import annotations

from app.config import settings


def _is_present(value: str) -> bool:
    return bool(value.strip())


def _llm_config_status() -> dict:
    provider = settings.llm_provider.strip().lower()
    required_settings = {
        "openai": [("OPENAI_API_KEY", settings.openai_api_key)],
        "anthropic": [("ANTHROPIC_API_KEY", settings.anthropic_api_key)],
        "gemini": [("GOOGLE_API_KEY", settings.google_api_key)],
        "openai_compatible": [
            ("OPENAI_COMPATIBLE_API_KEY", settings.openai_compatible_api_key),
            ("OPENAI_COMPATIBLE_BASE_URL", settings.openai_compatible_base_url),
        ],
        "ollama": [("OLLAMA_BASE_URL", settings.ollama_base_url)],
    }

    missing = [
        name
        for name, value in required_settings.get(provider, [])
        if not _is_present(value)
    ]
    unsupported = provider not in required_settings

    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "configured": not missing and not unsupported,
        "missing_settings": missing,
        "unsupported": unsupported,
    }


def _embedding_config_status() -> dict:
    provider = settings.embedding_provider.strip().lower()
    required_settings = {
        "openai": [("OPENAI_API_KEY", settings.openai_api_key)],
        "sentence_transformers": [],
    }

    missing = [
        name
        for name, value in required_settings.get(provider, [])
        if not _is_present(value)
    ]
    unsupported = provider not in required_settings

    return {
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "configured": not missing and not unsupported,
        "missing_settings": missing,
        "unsupported": unsupported,
    }


def build_health_details() -> dict:
    llm = _llm_config_status()
    embedding = _embedding_config_status()
    status = "ok" if llm["configured"] and embedding["configured"] else "degraded"

    return {
        "status": status,
        "service": "papertrail-api",
        "paths": {
            "data_dir": str(settings.data_dir),
            "database_path": str(settings.database_path),
            "chroma_dir": str(settings.chroma_dir),
        },
        "llm": llm,
        "embedding": embedding,
    }
