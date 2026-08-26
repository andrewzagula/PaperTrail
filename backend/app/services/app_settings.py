"""Reading and writing the settings a person chooses in the app.

Two rules hold this together:

  * `.env` is not rewritten. It records how this machine was set up, often by
    hand and with comments. Choices made in the app live in their own file and
    are layered on top, so reverting is deleting one file.
  * Nothing here reads, returns, or accepts a credential. Keys stay in `.env`.
    This module reports only whether the ones a provider needs are present,
    which is what the Settings screen needs to warn before you switch.
"""

from __future__ import annotations

import json
import os
import tempfile

from app.config import (
    EDITABLE_FIELDS,
    MODEL_FIELDS,
    PROVIDER_FIELDS,
    SETTINGS_FILE,
    WORKFLOW_MODEL_FIELDS,
    apply_stored_overrides,
    read_stored_overrides,
    settings,
)
from app.diagnostics import build_health_details, describe_providers

MAX_MODEL_LENGTH = 200

WORKFLOW_LABELS: dict[str, tuple[str, str]] = {
    "discovery_query_model": ("Discovery: writing queries", "Turns your question into arXiv searches"),
    "discovery_rank_model": ("Discovery: ranking results", "Reads many abstracts, so a cheap model earns its keep"),
    "analysis_model": ("Paper breakdown", ""),
    "chat_model": ("Paper chat", ""),
    "compare_profile_model": ("Compare: reading each paper", ""),
    "compare_synthesis_model": ("Compare: writing the summary", "Reads every profile at once"),
    "idea_generation_model": ("Ideas: generating", ""),
    "idea_critique_model": ("Ideas: critiquing", ""),
    "implementation_extraction_model": ("Plan: reading the method", ""),
    "implementation_code_model": ("Plan: writing starter code", ""),
    "implementation_review_model": ("Plan: reviewing", ""),
}


class SettingsValidationError(ValueError):
    """A submitted value this module refuses to store."""


def _clean_model(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise SettingsValidationError(f"{field} must be text.")
    cleaned = value.strip()
    if not cleaned:
        raise SettingsValidationError(f"{field} cannot be empty.")
    if len(cleaned) > MAX_MODEL_LENGTH:
        raise SettingsValidationError(
            f"{field} is longer than {MAX_MODEL_LENGTH} characters."
        )
    if any(character.isspace() and character != " " for character in cleaned):
        raise SettingsValidationError(f"{field} cannot contain line breaks or tabs.")
    return cleaned


def validate_patch(patch: dict) -> dict:
    """Return the subset of `patch` that is safe to store.

    Unknown fields are rejected rather than ignored, so a typo in a field name
    fails loudly instead of silently doing nothing.
    """
    if not isinstance(patch, dict):
        raise SettingsValidationError("Expected an object of settings to change.")

    unknown = sorted(set(patch) - set(EDITABLE_FIELDS))
    if unknown:
        raise SettingsValidationError(
            "Not a setting this screen can change: " + ", ".join(unknown)
        )

    cleaned: dict = {}

    for field, allowed in PROVIDER_FIELDS.items():
        if field not in patch:
            continue
        value = patch[field]
        if not isinstance(value, str) or value.strip().lower() not in allowed:
            raise SettingsValidationError(
                f"{field} must be one of: " + ", ".join(allowed)
            )
        cleaned[field] = value.strip().lower()

    for field in MODEL_FIELDS:
        if field in patch:
            cleaned[field] = _clean_model(patch[field], field=field)

    for field in WORKFLOW_MODEL_FIELDS:
        if field not in patch:
            continue
        value = patch[field]
        # null is the whole point: it means "follow the chat model", and it
        # keeps following it when the chat model changes later.
        cleaned[field] = None if value is None else _clean_model(value, field=field)

    return cleaned


def _write_overrides(overrides: dict) -> None:
    """Write the file whole, or not at all.

    A half-written settings file would be unreadable on the next start, and
    unreadable means every choice silently reverts to the .env defaults.
    """
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=SETTINGS_FILE.parent,
        prefix=SETTINGS_FILE.name,
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle:
            json.dump(overrides, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, SETTINGS_FILE)
    except BaseException:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def _reload_clients() -> None:
    """Drop the cached provider clients so the next request builds new ones.

    Each factory is `lru_cache(maxsize=1)`, so without this a settings change
    would take effect only after a restart, which is the thing this screen
    exists to avoid.
    """
    from app.llm.factory import (
        get_chat_client,
        get_embedding_client,
        get_structured_client,
    )

    get_chat_client.cache_clear()
    get_structured_client.cache_clear()
    get_embedding_client.cache_clear()


def update_settings(patch: dict) -> dict:
    """Validate, persist, apply, and drop the cached clients. In that order."""
    cleaned = validate_patch(patch)

    overrides = read_stored_overrides()
    overrides.update(cleaned)

    _write_overrides(overrides)
    apply_stored_overrides()
    _reload_clients()

    return describe_settings()


def reset_settings() -> dict:
    """Forget every choice made here and fall back to .env."""
    try:
        SETTINGS_FILE.unlink()
    except FileNotFoundError:
        pass

    # apply_stored_overrides only layers values on; it cannot restore one it
    # previously overwrote. Re-reading .env from a fresh Settings() is the only
    # honest way to get back to the defaults.
    from app.config import Settings

    defaults = Settings()
    for field in EDITABLE_FIELDS:
        setattr(settings, field, getattr(defaults, field))

    _reload_clients()
    return describe_settings()


def describe_settings() -> dict:
    """Everything the Settings screen renders, in one response."""
    overrides = read_stored_overrides()
    providers = describe_providers()

    workflows = []
    for field in WORKFLOW_MODEL_FIELDS:
        label, hint = WORKFLOW_LABELS[field]
        # Blank means inherit, wherever it came from: .env or this screen. The
        # resolved value rides along so the screen can say what will actually
        # run without doing the resolution itself.
        raw = (getattr(settings, field) or "").strip()
        workflows.append(
            {
                "field": field,
                "label": label,
                "hint": hint,
                "value": raw,
                "resolved": raw or settings.llm_model,
                "inherited": not raw,
            }
        )

    return {
        "chat": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "providers": providers["chat"],
        },
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "providers": providers["embedding"],
        },
        "workflows": workflows,
        # Which fields came from this screen rather than .env. The screen shows
        # it so a value you cannot account for is traceable to one of two files.
        "overridden": sorted(overrides),
        "health": build_health_details(),
    }
