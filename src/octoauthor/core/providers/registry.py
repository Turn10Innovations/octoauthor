"""Provider registry — maps ProviderType to provider classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from octoauthor.core.logging import get_logger
from octoauthor.core.models.providers import ProviderConfig, ProviderType

if TYPE_CHECKING:
    from octoauthor.core.providers.base import BaseProvider

logger = get_logger(__name__)

# Registry populated lazily to avoid importing optional SDKs at module load
_PROVIDER_MAP: dict[ProviderType, str] = {
    ProviderType.OLLAMA: "octoauthor.core.providers.ollama:OllamaProvider",
    ProviderType.ANTHROPIC: "octoauthor.core.providers.anthropic:AnthropicProvider",
    ProviderType.OPENAI: "octoauthor.core.providers.openai_compat:OpenAICompatProvider",
    ProviderType.GROQ: "octoauthor.core.providers.openai_compat:OpenAICompatProvider",
    ProviderType.GOOGLE: "octoauthor.core.providers.openai_compat:OpenAICompatProvider",
    ProviderType.CUSTOM: "octoauthor.core.providers.openai_compat:OpenAICompatProvider",
}


def _import_provider_class(dotted_path: str) -> type[BaseProvider]:
    """Import a provider class from a dotted module:class path."""
    module_path, class_name = dotted_path.rsplit(":", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)  # type: ignore[no-any-return]


def create_provider(config: ProviderConfig) -> BaseProvider:
    """Create a provider instance from config.

    Raises:
        ValueError: If the provider type is not registered.
        ImportError: If the provider SDK is not installed.
    """
    dotted_path = _PROVIDER_MAP.get(config.provider)
    if dotted_path is None:
        msg = f"No provider registered for type: {config.provider}"
        raise ValueError(msg)

    try:
        cls = _import_provider_class(dotted_path)
    except ImportError as e:
        msg = (
            f"Provider {config.provider} requires additional dependencies. "
            f"Install with: uv sync --extra providers-{config.provider}"
        )
        raise ImportError(msg) from e

    logger.info(
        "Creating provider",
        extra={"provider": config.provider.value, "model": config.model},
    )
    return cls(config)
