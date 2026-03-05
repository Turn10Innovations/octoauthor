"""Ollama provider — connects to a local Ollama instance via OpenAI-compatible API."""

from __future__ import annotations

import httpx

from octoauthor.core.logging import get_logger
from octoauthor.core.providers.base import BaseProvider, ProviderResponse

logger = get_logger(__name__)


class OllamaProvider(BaseProvider):
    """Provider for Ollama (local LLM server).

    Uses the OpenAI-compatible /v1/chat/completions endpoint that Ollama exposes.
    """

    def _get_base_url(self) -> str:
        return self.config.base_url or "http://localhost:11434"

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        images: list[bytes] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ProviderResponse:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "options": {
                "num_predict": max_tokens or self.config.max_tokens,
                "temperature": temperature if temperature is not None else self.config.temperature,
            },
            "stream": False,
        }

        base_url = self._get_base_url()
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        message_content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return ProviderResponse(
            text=message_content,
            model=self.config.model,
            provider="ollama",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    async def check_health(self) -> bool:
        base_url = self._get_base_url()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False
