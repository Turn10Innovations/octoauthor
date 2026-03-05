"""Configuration for visual-qa MCP server."""

from pydantic import Field
from pydantic_settings import BaseSettings


class VisualQAConfig(BaseSettings):
    """Visual QA server configuration."""

    model_config = {"env_prefix": "OCTOAUTHOR_VQA_"}

    expected_width: int = Field(default=1280, description="Expected screenshot width")
    expected_height: int = Field(default=800, description="Expected minimum screenshot height")
    max_file_size_kb: int = Field(default=500, description="Max screenshot file size in KB")
    allowed_formats: list[str] = Field(
        default_factory=lambda: ["png"],
        description="Allowed image formats",
    )
    diff_threshold: float = Field(
        default=0.05,
        description="Pixel difference threshold (0-1) for visual comparison",
    )
