"""Anthropic provider — connects to the Anthropic API."""

from __future__ import annotations

import base64
import os

from octoauthor.core.logging import get_logger
from octoauthor.core.providers.base import BaseProvider, ProviderResponse

logger = get_logger(__name__)


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude models.

    Requires the `anthropic` package: uv sync --extra providers-anthropic
    """

    def _get_client(self):  # type: ignore[no-untyped-def]
        try:
            import anthropic
        except ImportError as e:
            msg = "Anthropic provider requires the anthropic package. Install with: uv sync --extra providers-anthropic"
            raise ImportError(msg) from e

        api_key_env = self.config.api_key_env or "ANTHROPIC_API_KEY"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            msg = f"Anthropic API key not found in environment variable: {api_key_env}"
            raise ValueError(msg)

        return anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        images: list[bytes] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ProviderResponse:
        client = self._get_client()

        content: list[dict] = []  # type: ignore[type-arg]
        if images:
            for img_bytes in images:
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(img_bytes).decode(),
                        },
                    }
                )
        content.append({"type": "text", "text": prompt})

        kwargs: dict = {  # type: ignore[type-arg]
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "messages": [{"role": "user", "content": content}],
        }
        if system:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature
        else:
            kwargs["temperature"] = self.config.temperature

        response = await client.messages.create(**kwargs)

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        usage = response.usage
        return ProviderResponse(
            text=text,
            model=self.config.model,
            provider="anthropic",
            prompt_tokens=usage.input_tokens,
            completion_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + usage.output_tokens,
        )

    async def check_health(self) -> bool:
        try:
            self._get_client()
            return True
        except (ImportError, ValueError):
            return False
