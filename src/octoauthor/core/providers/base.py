"""Base provider abstraction for model-agnostic LLM access."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from octoauthor.core.models.providers import ProviderConfig


class ProviderResponse(BaseModel):
    """Standardized response from any LLM provider."""

    text: str = Field(description="Generated text content")
    model: str = Field(description="Model that generated the response")
    provider: str = Field(description="Provider backend name")
    prompt_tokens: int = Field(default=0, description="Prompt token count")
    completion_tokens: int = Field(default=0, description="Completion token count")
    total_tokens: int = Field(default=0, description="Total token count")


class BaseProvider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement the generate() method and return a
    ProviderResponse regardless of the underlying SDK.
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        images: list[bytes] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ProviderResponse:
        """Generate text from a prompt.

        Args:
            prompt: The user prompt.
            system: Optional system prompt.
            images: Optional list of image bytes for vision models.
            max_tokens: Override max tokens from config.
            temperature: Override temperature from config.

        Returns:
            Standardized ProviderResponse.
        """
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        """Check if the provider is reachable and configured correctly."""
        ...

    @property
    def model_name(self) -> str:
        return self.config.model

    @property
    def provider_name(self) -> str:
        return self.config.provider.value
