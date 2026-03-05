"""Shared test fixtures for OctoAuthor."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from octoauthor.core.config.settings import OctoAuthorSettings
from octoauthor.core.models.providers import ProviderConfig, ProviderType
from octoauthor.core.providers.base import BaseProvider, ProviderResponse


class MockProvider(BaseProvider):
    """Mock provider for testing — returns configurable responses."""

    def __init__(
        self,
        config: ProviderConfig | None = None,
        response_text: str = "Mock response",
    ) -> None:
        if config is None:
            config = ProviderConfig(
                provider=ProviderType.OLLAMA,
                model="mock-model",
                base_url="http://localhost:11434",
            )
        super().__init__(config)
        self.response_text = response_text
        self.generate_calls: list[dict] = []  # type: ignore[type-arg]

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        images: list[bytes] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ProviderResponse:
        self.generate_calls.append(
            {
                "prompt": prompt,
                "system": system,
                "images": images,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        return ProviderResponse(
            text=self.response_text,
            model=self.config.model,
            provider=self.config.provider.value,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

    async def check_health(self) -> bool:
        return True


@pytest.fixture
def mock_provider() -> MockProvider:
    """A mock LLM provider that records calls."""
    return MockProvider()


@pytest.fixture
def mock_provider_factory() -> type[MockProvider]:
    """The MockProvider class for creating custom instances."""
    return MockProvider


@pytest.fixture
def test_settings(tmp_path: Path) -> OctoAuthorSettings:
    """Settings configured for testing with temp directories."""
    return OctoAuthorSettings(
        debug=True,
        log_level="DEBUG",
        doc_output_dir=tmp_path / "docs",
        screenshot_output_dir=tmp_path / "screenshots",
        text_provider=ProviderType.OLLAMA,
        text_model="test-model",
        text_base_url="http://localhost:11434",
    )


@pytest.fixture
def tmp_docs_dir(tmp_path: Path) -> Path:
    """Temporary directory for doc output."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    return docs_dir


@pytest.fixture
def tmp_screenshots_dir(tmp_path: Path) -> Path:
    """Temporary directory for screenshot output."""
    ss_dir = tmp_path / "screenshots"
    ss_dir.mkdir()
    return ss_dir
