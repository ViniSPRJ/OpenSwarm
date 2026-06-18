"""Shared model configuration helpers — read by all agents at startup."""
import os


def get_default_model(fallback: str = "gpt-5.2"):
    """Return the configured default model for standard agents."""
    return _resolve(_default_model_name(fallback))


def get_orchestrator_model(fallback: str = "litellm/openrouter/openrouter/fusion"):
    """Return the configured model for the Portfolio Manager."""
    return _resolve(_orchestrator_model_name(fallback))


def get_specialist_model(fallback: str = "litellm/openrouter/deepseek/deepseek-v4-flash"):
    """Return the configured model for trading specialists."""
    return _resolve(_specialist_model_name(fallback))


def is_openai_provider() -> bool:
    """Return True when the configured provider is OpenAI (not LiteLLM).

    OpenAI model IDs never contain a slash (e.g. 'gpt-5.2', 'o3').
    Any 'provider/model' string (e.g. 'anthropic/claude-sonnet-4-6',
    'litellm/gemini/gemini-3-flash') is treated as a LiteLLM-routed model.
    """
    return _is_openai_model(_default_model_name())


def is_orchestrator_openai_provider() -> bool:
    return _is_openai_model(_orchestrator_model_name())


def is_specialist_openai_provider() -> bool:
    return _is_openai_model(_specialist_model_name())


def _default_model_name(fallback: str = "gpt-5.2") -> str:
    return os.getenv("DEFAULT_MODEL") or fallback


def _orchestrator_model_name(fallback: str = "litellm/openrouter/openrouter/fusion") -> str:
    return os.getenv("ORCHESTRATOR_MODEL") or os.getenv("DEFAULT_MODEL") or fallback


def _specialist_model_name(fallback: str = "litellm/openrouter/deepseek/deepseek-v4-flash") -> str:
    return os.getenv("SPECIALIST_MODEL") or os.getenv("DEFAULT_MODEL") or fallback


def _is_openai_model(model: str) -> bool:
    return "/" not in model


def _resolve(model: str):
    """Route 'provider/model' strings through LitellmModel.

    Handles both explicit 'litellm/<model>' and bare 'provider/model' forms.
    OpenAI model IDs contain no slash, so they pass through unchanged.
    """
    if "/" not in model:
        return model
    bare = model[len("litellm/"):] if model.startswith("litellm/") else model
    try:
        from agency_swarm import LitellmModel  # noqa: PLC0415
        return LitellmModel(model=bare)
    except ImportError:
        return model
