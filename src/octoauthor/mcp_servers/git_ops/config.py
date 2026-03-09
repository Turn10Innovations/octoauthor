"""Git ops server configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitOpsConfig(BaseSettings):
    """Configuration for the git-ops MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="OCTOAUTHOR_",
        case_sensitive=False,
    )

    github_branch_prefix: str = Field(
        default="octoauthor/doc-update",
        description="Prefix for auto-created branches",
    )
