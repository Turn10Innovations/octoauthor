"""Tests for provider abstraction layer."""

from __future__ import annotations

import pytest

from octoauthor.core.models.providers import ProviderConfig, ProviderType
from octoauthor.core.providers.base import ProviderResponse
from octoauthor.core.providers.registry import create_provider


class TestProviderResponse:
    def test_creation(self) -> None:
        resp = ProviderResponse(
            text="Hello world",
            model="test-model",
            provider="ollama",
            prompt_tokens=5,
            completion_tokens=10,
            total_tokens=15,
        )
        assert resp.text == "Hello world"
        assert resp.total_tokens == 15

    def test_defaults(self) -> None:
        resp = ProviderResponse(text="Hi", model="m", provider="p")
        assert resp.prompt_tokens == 0
        assert resp.total_tokens == 0


class TestProviderRegistry:
    def test_create_ollama_provider(self) -> None:
        config = ProviderConfig(
            provider=ProviderType.OLLAMA,
            model="qwen3:32b",
            base_url="http://localhost:11434",
        )
        provider = create_provider(config)
        assert provider.model_name == "qwen3:32b"
        assert provider.provider_name == "ollama"

    def test_create_openai_compat_provider(self) -> None:
        config = ProviderConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4o",
        )
        provider = create_provider(config)
        assert provider.provider_name == "openai"

    def test_create_groq_uses_openai_compat(self) -> None:
        config = ProviderConfig(
            provider=ProviderType.GROQ,
            model="llama-3.1-70b",
        )
        provider = create_provider(config)
        assert provider.provider_name == "groq"


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_generate(self, mock_provider) -> None:  # type: ignore[no-untyped-def]
        response = await mock_provider.generate("test prompt")
        assert response.text == "Mock response"
        assert response.model == "mock-model"
        assert len(mock_provider.generate_calls) == 1
        assert mock_provider.generate_calls[0]["prompt"] == "test prompt"

    @pytest.mark.asyncio
    async def test_generate_with_system(self, mock_provider) -> None:  # type: ignore[no-untyped-def]
        response = await mock_provider.generate("test", system="You are helpful")
        assert response.text == "Mock response"
        assert mock_provider.generate_calls[0]["system"] == "You are helpful"

    @pytest.mark.asyncio
    async def test_health_check(self, mock_provider) -> None:  # type: ignore[no-untyped-def]
        assert await mock_provider.check_health() is True

    @pytest.mark.asyncio
    async def test_custom_response(self, mock_provider_factory) -> None:  # type: ignore[no-untyped-def]
        provider = mock_provider_factory(response_text="Custom output")
        response = await provider.generate("input")
        assert response.text == "Custom output"
