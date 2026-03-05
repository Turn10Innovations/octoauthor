"""Configuration for app-inspector MCP server."""

from pydantic import Field
from pydantic_settings import BaseSettings


class AppInspectorConfig(BaseSettings):
    """App inspector server configuration."""

    model_config = {"env_prefix": "OCTOAUTHOR_INSPECTOR_"}

    navigation_timeout: int = Field(default=30000, description="Navigation timeout in ms")
    wait_timeout: int = Field(default=5000, description="Element wait timeout in ms")
    max_depth: int = Field(default=5, description="Max depth for DOM tree extraction")
    max_elements: int = Field(default=500, description="Max elements to return per inspection")
