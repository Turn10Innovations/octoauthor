"""Doc writer server configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocWriterConfig(BaseSettings):
    """Configuration for the doc-writer MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="OCTOAUTHOR_",
        case_sensitive=False,
    )

    template_dir: Path = Field(
        default=Path(__file__).parent / "templates",
        description="Directory containing Jinja2 templates",
    )
    specs_dir: Path = Field(
        default=Path("specs"),
        description="Directory containing spec files",
    )
    max_steps_per_guide: int = Field(default=10, description="Max steps per guide")
    max_guide_length_words: int = Field(default=1500, description="Max words per guide")
