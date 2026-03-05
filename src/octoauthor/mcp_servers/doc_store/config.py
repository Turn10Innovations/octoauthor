"""Doc store server configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocStoreConfig(BaseSettings):
    """Configuration for the doc-store MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="OCTOAUTHOR_",
        case_sensitive=False,
    )

    doc_output_dir: Path = Field(
        default=Path("docs/user-guide"),
        description="Root directory for stored documentation",
    )
    screenshot_output_dir: Path = Field(
        default=Path("docs/user-guide/assets"),
        description="Directory for stored screenshots",
    )
    manifest_filename: str = Field(
        default="manifest.yaml",
        description="Name of the manifest index file",
    )
