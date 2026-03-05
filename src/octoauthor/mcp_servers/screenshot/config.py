"""Screenshot server configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScreenshotConfig(BaseSettings):
    """Configuration for the screenshot MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="OCTOAUTHOR_",
        case_sensitive=False,
    )

    viewport_width: int = Field(default=1280, description="Browser viewport width")
    viewport_height: int = Field(default=800, description="Browser viewport height")
    light_mode_only: bool = Field(default=True, description="Force light mode for captures")
    max_screenshot_size_kb: int = Field(default=500, description="Max screenshot file size in KB")
    strip_exif: bool = Field(default=True, description="Strip EXIF metadata from screenshots")
    screenshot_output_dir: str = Field(
        default="docs/user-guide/assets",
        description="Directory for screenshot output",
    )
    navigation_timeout_ms: int = Field(default=30000, description="Page navigation timeout in ms")
    wait_after_load_ms: int = Field(default=1000, description="Wait time after page load before capture")
