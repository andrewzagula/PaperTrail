from __future__ import annotations

from app.config import settings

# Substrings that mark a setting as copied-but-not-filled-in. A value like
# "sk-your-openai-api-key-here" is non-empty, so a presence check alone
# reports a fully configured deployment that fails on the first real request.
PLACEHOLDER_MARKERS = (
    "your-",
    "your_",
    "-here",
    "_here",
    "changeme",
    "change-me",
    "replace-me",
    "replaceme",
    "placeholder",
    "xxxx",
    "<",
    ">",
)

CREDENTIAL_NOT_CHECKED = "not_checked"
CREDENTIAL_OK = "ok"
CREDENTIAL_FAILED = "failed"
CREDENTIAL_SKIPPED = "skipped"


def _is_present(value: str) -> bool:
    return bool(value.strip())


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _redact(text: str) -> str:
    """Remove any configured secret that a provider echoed back to us."""
    secrets = (
        settings.openai_api_key,
        settings.openai_compatible_api_key,
        settings.anthropic_api_key,
        settings.google_api_key,
    )
    for secret in secrets:
        if secret and secret.strip():
            text = text.replace(secret.strip(), "[redacted]")
    return text


def _required_llm_settings(provider: str) -> list[tuple[str, str]] | None:
    required = {
        "openai": [("OPENAI_API_KEY", settings.openai_api_key)],
        "anthropic": [("ANTHROPIC_API_KEY", settings.anthropic_api_key)],
        "gemini": [("GOOGLE_API_KEY", settings.google_api_key)],
        "openai_compatible": [
            ("OPENAI_COMPATIBLE_API_KEY", settings.openai_compatible_api_key),
            ("OPENAI_COMPATIBLE_BASE_URL", settings.openai_compatible_base_url),
        ],
        "ollama": [("OLLAMA_BASE_URL", settings.ollama_base_url)],
    }
    return required.get(provider)


def _required_embedding_settings(provider: str) -> list[tuple[str, str]] | None:
    required = {
        "openai": [("OPENAI_API_KEY", settings.openai_api_key)],
        "sentence_transformers": [],
    }
    return required.get(provider)


def _config_status(provider_setting: str, model: str, required) -> dict:
    provider = provider_setting.strip().lower()
    required_settings = required(provider)
    unsupported = required_settings is None
    required_settings = required_settings or []

    missing = [
        name for name, value in required_settings if not _is_present(value)
    ]
    placeholders = [
        name
        for name, value in required_settings
        if _is_present(value) and _looks_like_placeholder(value)
    ]

    return {
        "provider": provider_setting,
        "model": model,
        "configured": not missing and not placeholders and not unsupported,
        "missing_settings": missing,
        # Present but obviously unedited. Reported separately from missing so
        # the fix ("you copied .env.example but never pasted your key") is
        # distinguishable from "you set nothing at all".
        "placeholder_settings": placeholders,
        "unsupported": unsupported,
        "credential_check": {"status": CREDENTIAL_NOT_CHECKED, "detail": ""},
    }


def _llm_config_status() -> dict:
    return _config_status(
        settings.llm_provider, settings.llm_model, _required_llm_settings
    )


def _embedding_config_status() -> dict:
    return _config_status(
        settings.embedding_provider,
        settings.embedding_model,
        _required_embedding_settings,
    )


def _probe_llm() -> dict:
    from app.llm import get_chat_client

    get_chat_client().generate(
        [{"role": "user", "content": "ping"}], temperature=0.0
    )
    return {"status": CREDENTIAL_OK, "detail": "Provider accepted a test request."}


def _probe_embedding() -> dict:
    from app.llm import get_embedding_client

    get_embedding_client().embed_query("ping")
    return {"status": CREDENTIAL_OK, "detail": "Provider accepted a test request."}


def _run_probe(config: dict, probe) -> dict:
    if not config["configured"]:
        return {
            "status": CREDENTIAL_SKIPPED,
            "detail": "Settings are incomplete, so no request was attempted.",
        }

    try:
        return probe()
    except Exception as error:  # provider SDKs raise many unrelated types
        detail = _redact(f"{type(error).__name__}: {error}")
        return {"status": CREDENTIAL_FAILED, "detail": detail[:300]}


def build_health_details(probe: bool = False) -> dict:
    llm = _llm_config_status()
    embedding = _embedding_config_status()

    if probe:
        llm["credential_check"] = _run_probe(llm, _probe_llm)
        embedding["credential_check"] = _run_probe(embedding, _probe_embedding)

    configured = llm["configured"] and embedding["configured"]
    probe_failed = (
        llm["credential_check"]["status"] == CREDENTIAL_FAILED
        or embedding["credential_check"]["status"] == CREDENTIAL_FAILED
    )
    status = "ok" if configured and not probe_failed else "degraded"

    return {
        "status": status,
        "service": "papertrail-api",
        # Settings look right. Only a probe run proves the credentials work.
        "credentials_verified": (
            llm["credential_check"]["status"] == CREDENTIAL_OK
            and embedding["credential_check"]["status"] == CREDENTIAL_OK
        ),
        "paths": {
            "data_dir": str(settings.data_dir),
            "database_path": str(settings.database_path),
            "chroma_dir": str(settings.chroma_dir),
        },
        "llm": llm,
        "embedding": embedding,
    }
