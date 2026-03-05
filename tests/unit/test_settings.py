"""Tests for application settings."""

from pathlib import Path

import pytest

from octoauthor.core.config.settings import OctoAuthorSettings
from octoauthor.core.models.providers import ProviderType


class TestOctoAuthorSettings:
    def test_defaults(self) -> None:
        settings = OctoAuthorSettings()
        assert settings.app_name == "OctoAuthor"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.doc_output_dir == Path("docs/user-guide")
        assert settings.text_provider == ProviderType.OLLAMA
        assert settings.text_model == "qwen3:32b"
        assert settings.strip_exif is True

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OCTOAUTHOR_DEBUG", "true")
        monkeypatch.setenv("OCTOAUTHOR_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("OCTOAUTHOR_TEXT_MODEL", "llama3:8b")
        settings = OctoAuthorSettings()
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.text_model == "llama3:8b"

    def test_get_text_provider_config(self) -> None:
        settings = OctoAuthorSettings()
        config = settings.get_text_provider_config()
        assert config.provider == ProviderType.OLLAMA
        assert config.model == "qwen3:32b"
        assert config.base_url == "http://localhost:11434"

    def test_custom_output_dirs(self, tmp_path: Path) -> None:
        settings = OctoAuthorSettings(
            doc_output_dir=tmp_path / "custom-docs",
            screenshot_output_dir=tmp_path / "custom-ss",
        )
        assert settings.doc_output_dir == tmp_path / "custom-docs"
        assert settings.screenshot_output_dir == tmp_path / "custom-ss"

    def test_url_allowlist_default_empty(self) -> None:
        settings = OctoAuthorSettings()
        assert settings.url_allowlist == []

    def test_github_settings(self) -> None:
        settings = OctoAuthorSettings()
        assert settings.github_branch_prefix == "openclaw/doc-update"
