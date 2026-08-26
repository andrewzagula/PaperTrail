import json
import os
from pathlib import Path

from pydantic_settings import BaseSettings

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Choices made in the app, layered on top of .env rather than rewritten into
# it. Keeping them apart means "how this machine was set up" and "what I picked
# in Settings" stay legible as separate things, and reverting is deleting one
# file rather than un-editing a dotfile.
SETTINGS_FILE = DATA_DIR / "settings.json"

CHAT_PROVIDERS = ("openai", "anthropic", "gemini", "openai_compatible", "ollama")
EMBEDDING_PROVIDERS = ("openai", "sentence_transformers")

PROVIDER_FIELDS = {
    "llm_provider": CHAT_PROVIDERS,
    "embedding_provider": EMBEDDING_PROVIDERS,
}
MODEL_FIELDS = ("llm_model", "embedding_model")

# Each of these may instead be null, meaning "follow the chat model". That
# resolves to an empty string on the settings object, because the provider
# clients already read an empty model as "use the default" and a second
# convention for the same idea is one too many.
WORKFLOW_MODEL_FIELDS = (
    "discovery_query_model",
    "discovery_rank_model",
    "analysis_model",
    "chat_model",
    "compare_profile_model",
    "compare_synthesis_model",
    "idea_generation_model",
    "idea_critique_model",
    "implementation_extraction_model",
    "implementation_code_model",
    "implementation_review_model",
)

EDITABLE_FIELDS = tuple(PROVIDER_FIELDS) + MODEL_FIELDS + WORKFLOW_MODEL_FIELDS


def read_stored_overrides() -> dict:
    """Settings chosen in the app. Missing or unreadable means none."""
    try:
        with SETTINGS_FILE.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: value for key, value in data.items() if key in EDITABLE_FIELDS}


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_compatible_api_key: str = ""
    openai_compatible_base_url: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    local_embedding_device: str = ""

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    discovery_query_model: str = "gpt-4o-mini"
    discovery_rank_model: str = "gpt-4o-mini"
    analysis_model: str = "gpt-4o-mini"
    chat_model: str = "gpt-4o-mini"
    compare_profile_model: str = "gpt-4o-mini"
    compare_synthesis_model: str = "gpt-4o"
    idea_generation_model: str = "gpt-4o-mini"
    idea_critique_model: str = "gpt-4o-mini"
    implementation_extraction_model: str = "gpt-4o-mini"
    implementation_code_model: str = "gpt-4o-mini"
    implementation_review_model: str = "gpt-4o-mini"

    data_dir: Path = DATA_DIR
    database_path: Path = DATA_DIR / "papertrail.db"
    chroma_dir: Path = DATA_DIR / "chroma"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"

    model_config = {
        "env_file": os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
        ),
        "env_file_encoding": "utf-8",
    }


settings = Settings()


def apply_stored_overrides() -> dict:
    """Layer the stored choices onto the live settings object.

    Returns the overrides it applied, so a caller can tell which values came
    from here rather than from .env.
    """
    overrides = read_stored_overrides()

    for field in tuple(PROVIDER_FIELDS) + MODEL_FIELDS:
        value = overrides.get(field)
        if isinstance(value, str) and value.strip():
            setattr(settings, field, value.strip())

    for field in WORKFLOW_MODEL_FIELDS:
        if field not in overrides:
            continue
        value = overrides[field]
        setattr(
            settings,
            field,
            value.strip() if isinstance(value, str) and value.strip() else "",
        )

    return overrides


apply_stored_overrides()
