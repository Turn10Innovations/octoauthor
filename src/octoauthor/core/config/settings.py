"""Application settings using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from octoauthor.core.models.providers import ProviderConfig, ProviderType


class OctoAuthorSettings(BaseSettings):
    """Top-level application settings. Loaded from env vars and .env file."""

    model_config = SettingsConfigDict(
        env_prefix="OCTOAUTHOR_",
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # General
    app_name: str = Field(default="OctoAuthor", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Output
    doc_output_dir: Path = Field(
        default=Path("docs/user-guide"),
        description="Directory where generated docs are written",
    )
    screenshot_output_dir: Path = Field(
        default=Path("docs/user-guide/assets"),
        description="Directory where screenshots are stored",
    )

    # Providers (configured via env vars or config file)
    text_provider: ProviderType = Field(default=ProviderType.OLLAMA, description="Text generation provider")
    text_model: str = Field(default="qwen3:32b", description="Text generation model")
    text_base_url: str | None = Field(default="http://localhost:11434", description="Text provider base URL")

    vision_provider: ProviderType | None = Field(default=None, description="Vision provider (optional)")
    vision_model: str | None = Field(default=None, description="Vision model")

    qa_provider: ProviderType | None = Field(default=None, description="QA review provider (optional)")
    qa_model: str | None = Field(default=None, description="QA review model")

    audit_provider: ProviderType = Field(
        default=ProviderType.ANTHROPIC, description="Audit provider (should be strong)"
    )
    audit_model: str = Field(default="claude-sonnet-4-6", description="Audit model")

    # API Keys
    api_key: str | None = Field(default=None, description="API key for orchestrator authentication")
    auditor_api_key: str | None = Field(default=None, description="API key for the auditor agent")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key for LLM providers")

    # GitHub integration
    github_token: str | None = Field(default=None, description="GitHub PAT for PR operations")
    github_branch_prefix: str = Field(
        default="openclaw/doc-update",
        description="Prefix for auto-created branches",
    )

    # Ports — configurable to avoid conflicts with other services
    api_port: int = Field(default=9210, description="Discovery API port")
    mcp_port_screenshot: int = Field(default=9211, description="Screenshot MCP server port")
    mcp_port_doc_writer: int = Field(default=9212, description="Doc writer MCP server port")
    mcp_port_doc_store: int = Field(default=9213, description="Doc store MCP server port")
    mcp_port_visual_qa: int = Field(default=9214, description="Visual QA MCP server port")
    mcp_port_app_inspector: int = Field(default=9215, description="App inspector MCP server port")

    # Security
    url_allowlist: list[str] = Field(
        default_factory=list,
        description="Allowed external URL domains in generated docs",
    )
    max_screenshot_size_kb: int = Field(default=500, description="Max screenshot file size in KB")
    strip_exif: bool = Field(default=True, description="Strip EXIF metadata from screenshots")

    def get_text_provider_config(self) -> ProviderConfig:
        return ProviderConfig(
            provider=self.text_provider,
            model=self.text_model,
            base_url=self.text_base_url,
        )


@lru_cache
def get_settings() -> OctoAuthorSettings:
    """Get cached application settings."""
    return OctoAuthorSettings()
