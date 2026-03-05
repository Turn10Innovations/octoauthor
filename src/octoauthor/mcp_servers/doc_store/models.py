"""Pydantic models for doc-store MCP server inputs/outputs."""

from datetime import date

from pydantic import BaseModel, Field


class StoreDocInput(BaseModel):
    """Input for the store_doc tool."""

    tag: str = Field(description="Unique doc tag (kebab-case)")
    title: str = Field(description="Human-readable title")
    version: str = Field(description="App version this doc targets")
    applies_to: list[str] = Field(description="Products this doc applies to")
    route: str = Field(description="App route this doc covers")
    category: str = Field(default="general", description="Doc category")
    content_markdown: str = Field(description="Full markdown content")


class StoreDocResult(BaseModel):
    """Result from the store_doc tool."""

    tag: str
    path: str
    manifest_updated: bool = True


class GetDocResult(BaseModel):
    """Result from the get_doc tool."""

    tag: str
    title: str
    version: str
    content_markdown: str
    last_updated: date
    screenshot_count: int = 0


class DocListEntry(BaseModel):
    """Single entry in the doc listing."""

    tag: str
    title: str
    version: str
    last_updated: date
    route: str
    category: str
    screenshot_count: int = 0


class ManifestEntry(BaseModel):
    """A single entry in the manifest.yaml file."""

    tag: str
    title: str
    version: str
    last_updated: date
    route: str
    category: str
    applies_to: list[str]
    screenshot_count: int = 0
    filename: str = Field(description="Markdown filename relative to doc dir")


class StoreScreenshotInput(BaseModel):
    """Input for the store_screenshot tool."""

    tag: str = Field(description="Doc tag this screenshot belongs to")
    filename: str = Field(description="Screenshot filename (e.g., 'company-list-01.png')")
    data_base64: str = Field(description="Base64-encoded PNG image data")
    alt_text: str = Field(default="", description="Accessibility alt text")
    step_number: int | None = Field(default=None, description="Step number this screenshot illustrates")


class StoreScreenshotResult(BaseModel):
    """Result from the store_screenshot tool."""

    path: str
    size_kb: float
