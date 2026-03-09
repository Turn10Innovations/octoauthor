"""Tests for application settings."""

from pathlib import Path

import pytest

from octoauthor.core.config.settings import OctoAuthorSettings
from octoauthor.core.models.providers import ProviderType


def _clean_settings(**kwargs: object) -> OctoAuthorSettings:
    """Create settings without loading .env file (for deterministic tests)."""
    return OctoAuthorSettings(_env_file=None, **kwargs)  # type: ignore[call-arg]


class TestOctoAuthorSettings:
    def test_defaults(self) -> None:
        settings = _clean_settings()
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
        settings = _clean_settings()
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.text_model == "llama3:8b"

    def test_get_text_provider_config(self) -> None:
        settings = _clean_settings()
        config = settings.get_text_provider_config()
        assert config.provider == ProviderType.OLLAMA
        assert config.model == "qwen3:32b"
        assert config.base_url == "http://localhost:11434"

    def test_custom_output_dirs(self, tmp_path: Path) -> None:
        settings = _clean_settings(
            doc_output_dir=tmp_path / "custom-docs",
            screenshot_output_dir=tmp_path / "custom-ss",
        )
        assert settings.doc_output_dir == tmp_path / "custom-docs"
        assert settings.screenshot_output_dir == tmp_path / "custom-ss"

    def test_url_allowlist_default_empty(self) -> None:
        settings = _clean_settings()
        assert settings.url_allowlist == []

    def test_github_settings(self) -> None:
        settings = _clean_settings()
        assert settings.github_branch_prefix == "octoauthor/doc-update"

    def test_port_defaults(self) -> None:
        settings = _clean_settings()
        assert settings.api_port == 9210
        assert settings.mcp_port_screenshot == 9211
        assert settings.mcp_port_doc_writer == 9212
        assert settings.mcp_port_doc_store == 9213
        assert settings.mcp_port_visual_qa == 9214
        assert settings.mcp_port_app_inspector == 9215

    def test_port_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OCTOAUTHOR_API_PORT", "7000")
        monkeypatch.setenv("OCTOAUTHOR_MCP_PORT_SCREENSHOT", "7001")
        settings = _clean_settings()
        assert settings.api_port == 7000
        assert settings.mcp_port_screenshot == 7001
