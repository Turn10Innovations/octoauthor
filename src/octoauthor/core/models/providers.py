"""Provider models - configuration for model-agnostic LLM access."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ProviderType(StrEnum):
    """Supported LLM provider backends."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    GROQ = "groq"
    GOOGLE = "google"
    CUSTOM = "custom"  # For any OpenAI-compatible endpoint


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    provider: ProviderType = Field(description="Provider backend")
    model: str = Field(description="Model identifier (e.g., 'claude-sonnet-4-6', 'qwen3:32b')")
    base_url: str | None = Field(default=None, description="Custom base URL (required for ollama, custom)")
    api_key_env: str | None = Field(
        default=None,
        description="Environment variable name containing the API key (e.g., 'ANTHROPIC_API_KEY')",
    )
    max_tokens: int = Field(default=4096, description="Max tokens for generation")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="Generation temperature")
    supports_vision: bool = Field(default=False, description="Whether this model supports image inputs")


class ProvidersConfig(BaseModel):
    """Top-level provider configuration mapping capabilities to providers."""

    text: ProviderConfig = Field(description="Provider for text generation (writing docs)")
    vision: ProviderConfig | None = Field(default=None, description="Provider for vision tasks (screenshot analysis)")
    qa: ProviderConfig | None = Field(default=None, description="Provider for QA review (style/quality checks)")
    audit: ProviderConfig | None = Field(
        default=None,
        description="Provider for security audit (MUST be a strong model)",
    )
