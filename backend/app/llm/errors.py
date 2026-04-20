from __future__ import annotations


CONFIGURATION_ERROR_DETAIL = "LLM provider is not configured correctly for this deployment."
REQUEST_ERROR_DETAIL = "LLM provider request failed. Please try again."


class LLMProviderError(RuntimeError):
    pass


class ProviderConfigurationError(LLMProviderError):
    pass


class UnsupportedProviderError(ProviderConfigurationError):
    pass


class MissingProviderCredentialsError(ProviderConfigurationError):
    pass


class MissingProviderDependencyError(ProviderConfigurationError):
    pass


class InvalidProviderConfigError(ProviderConfigurationError):
    pass


class ProviderRequestError(LLMProviderError):
    pass


def get_provider_error_response(error: Exception) -> tuple[int, str] | None:
    if isinstance(error, ProviderConfigurationError):
        return 503, CONFIGURATION_ERROR_DETAIL

    if isinstance(error, ProviderRequestError):
        return 502, REQUEST_ERROR_DETAIL

    return None
