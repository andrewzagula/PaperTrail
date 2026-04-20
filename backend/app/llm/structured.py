from __future__ import annotations

import json
from typing import Callable

from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as validate_json_schema

from app.llm.base import LLMMessage
from app.llm.errors import ProviderRequestError


class StructuredOutputError(ProviderRequestError):
    pass


class StructuredParseError(StructuredOutputError):
    pass


class StructuredValidationError(StructuredOutputError):
    pass


NativeStructuredGenerator = Callable[[list[LLMMessage], str | None, float, dict], dict]
RawTextGenerator = Callable[[list[LLMMessage], str | None, float], str]


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if not lines:
        return stripped

    lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_json_object(text: str) -> dict:
    cleaned = strip_code_fences(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise StructuredParseError("Model did not return valid JSON.") from error

    if not isinstance(payload, dict):
        raise StructuredParseError("Model did not return a JSON object.")

    return payload


def validate_json_object(payload: dict, schema: dict) -> dict:
    try:
        validate_json_schema(instance=payload, schema=schema)
    except JSONSchemaValidationError as error:
        raise StructuredValidationError(error.message) from error
    return payload


def build_json_messages(
    messages: list[LLMMessage],
    *,
    schema_name: str,
    schema: dict,
) -> list[LLMMessage]:
    schema_json = json.dumps(schema, ensure_ascii=True)
    guidance: LLMMessage = {
        "role": "system",
        "content": (
            f"Return ONLY a valid JSON object for schema '{schema_name}'. "
            "Do not include markdown fences or explanatory text.\n\n"
            f"JSON Schema:\n{schema_json}"
        ),
    }
    return [guidance, *messages]


def build_repair_messages(
    messages: list[LLMMessage],
    *,
    schema_name: str,
    schema: dict,
    invalid_response: str,
    error: Exception,
) -> list[LLMMessage]:
    repair_prompt: LLMMessage = {
        "role": "user",
        "content": (
            f"Your previous response did not satisfy schema '{schema_name}'. "
            f"Validation error: {error}. Return ONLY a corrected JSON object."
        ),
    }
    return [
        *build_json_messages(messages, schema_name=schema_name, schema=schema),
        {"role": "assistant", "content": invalid_response},
        repair_prompt,
    ]


def generate_structured_payload(
    *,
    messages: list[LLMMessage],
    schema_name: str,
    schema: dict,
    native_generate: NativeStructuredGenerator,
    text_generate: RawTextGenerator,
    model: str | None = None,
    temperature: float = 0.2,
) -> dict:
    native_error: Exception | None = None

    try:
        payload = native_generate(messages, model, temperature, schema)
        return validate_json_object(payload, schema)
    except Exception as error:
        native_error = error

    json_messages = build_json_messages(
        messages,
        schema_name=schema_name,
        schema=schema,
    )

    try:
        raw_response = text_generate(json_messages, model, temperature)
        payload = parse_json_object(raw_response)
        return validate_json_object(payload, schema)
    except StructuredOutputError as error:
        repair_messages = build_repair_messages(
            messages,
            schema_name=schema_name,
            schema=schema,
            invalid_response=raw_response,
            error=error,
        )
    except ProviderRequestError:
        raise
    except Exception as error:
        raise StructuredOutputError(
            f"Structured generation failed for schema '{schema_name}' during JSON fallback."
        ) from error

    try:
        repaired_response = text_generate(repair_messages, model, temperature)
        payload = parse_json_object(repaired_response)
        return validate_json_object(payload, schema)
    except ProviderRequestError:
        raise
    except Exception as error:
        native_detail = (
            f" Native attempt error: {type(native_error).__name__}: {native_error}"
            if native_error is not None
            else ""
        )
        raise StructuredOutputError(
            f"Structured generation failed for schema '{schema_name}' after repair.{native_detail}"
        ) from error
