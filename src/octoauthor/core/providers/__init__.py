"""Provider abstraction layer — model-agnostic LLM access.

Usage:
    from octoauthor.core.providers import get_provider
    provider = get_provider("text")
    response = await provider.generate(prompt="...")
"""

from __future__ import annotations

from octoauthor.core.providers.base import BaseProvider, ProviderResponse
from octoauthor.core.providers.registry import create_provider

__all__ = ["BaseProvider", "ProviderResponse", "create_provider", "get_provider"]


def get_provider(capability: str) -> BaseProvider:
    """Get a provider for the given capability (text, vision, qa, audit).

    Resolves provider configuration from application settings.

    Args:
        capability: One of "text", "vision", "qa", "audit".

    Returns:
        A configured BaseProvider instance.

    Raises:
        ValueError: If the capability is not configured.
    """
    from octoauthor.core.config import get_settings
    from octoauthor.core.models.providers import ProviderConfig

    settings = get_settings()

    config_map: dict[str, ProviderConfig | None] = {
        "text": settings.get_text_provider_config(),
    }

    # Vision, QA, Audit — build config if fields are set
    if settings.vision_provider and settings.vision_model:
        config_map["vision"] = ProviderConfig(
            provider=settings.vision_provider,
            model=settings.vision_model,
            supports_vision=True,
        )
    if settings.qa_provider and settings.qa_model:
        config_map["qa"] = ProviderConfig(
            provider=settings.qa_provider,
            model=settings.qa_model,
        )
    config_map["audit"] = ProviderConfig(
        provider=settings.audit_provider,
        model=settings.audit_model,
    )

    config = config_map.get(capability)
    if config is None:
        msg = f"No provider configured for capability: {capability}"
        raise ValueError(msg)

    return create_provider(config)
