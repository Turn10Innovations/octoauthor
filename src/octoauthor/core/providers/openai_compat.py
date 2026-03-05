"""OpenAI-compatible provider — works with OpenAI, Groq, and custom endpoints."""

from __future__ import annotations

import os

import httpx

from octoauthor.core.logging import get_logger
from octoauthor.core.models.providers import ProviderType
from octoauthor.core.providers.base import BaseProvider, ProviderResponse

logger = get_logger(__name__)

_DEFAULT_BASE_URLS: dict[ProviderType, str] = {
    ProviderType.OPENAI: "https://api.openai.com/v1",
    ProviderType.GROQ: "https://api.groq.com/openai/v1",
}

_DEFAULT_API_KEY_ENVS: dict[ProviderType, str] = {
    ProviderType.OPENAI: "OPENAI_API_KEY",
    ProviderType.GROQ: "GROQ_API_KEY",
    ProviderType.GOOGLE: "GOOGLE_API_KEY",
}


class OpenAICompatProvider(BaseProvider):
    """Provider for any OpenAI-compatible API (OpenAI, Groq, custom endpoints)."""

    def _get_base_url(self) -> str:
        if self.config.base_url:
            return self.config.base_url
        return _DEFAULT_BASE_URLS.get(self.config.provider, "http://localhost:8080/v1")

    def _get_api_key(self) -> str | None:
        env_var = self.config.api_key_env or _DEFAULT_API_KEY_ENVS.get(self.config.provider)
        if env_var:
            return os.environ.get(env_var)
        return None

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        images: list[bytes] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ProviderResponse:
        messages: list[dict] = []  # type: ignore[type-arg]
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
        }

        base_url = self._get_base_url()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        api_key = self._get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        text = choice["message"]["content"]
        usage = data.get("usage", {})

        return ProviderResponse(
            text=text,
            model=self.config.model,
            provider=self.config.provider.value,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

    async def check_health(self) -> bool:
        base_url = self._get_base_url()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{base_url}/models")
                return response.status_code == 200
        except httpx.HTTPError:
            return False
