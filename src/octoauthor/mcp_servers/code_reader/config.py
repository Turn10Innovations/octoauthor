"""Code reader server configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CodeReaderConfig(BaseSettings):
    """Configuration for the code-reader MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="OCTOAUTHOR_",
        case_sensitive=False,
    )

    code_source_type: str = Field(
        default="local",
        description="Code source: 'local' (filesystem) or 'github' (API)",
    )
    code_source_path: str = Field(
        default=".",
        description="Local path to repo root, or GitHub 'owner/repo' for github source",
    )
    code_github_ref: str = Field(
        default="main",
        description="Git ref (branch/tag/sha) for GitHub source",
    )
