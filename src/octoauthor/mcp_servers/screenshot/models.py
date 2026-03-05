"""Pydantic models for screenshot MCP server inputs/outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CaptureScreenshotInput(BaseModel):
    """Input for the capture_screenshot tool."""

    url: str = Field(description="Full URL to navigate to and capture")
    output_filename: str = Field(description="Output filename (e.g., 'company-list-01.png')")
    wait_for: str | None = Field(default=None, description="CSS selector to wait for before capture")
    full_page: bool = Field(default=False, description="Capture the full scrollable page")


class CaptureScreenshotResult(BaseModel):
    """Result from the capture_screenshot tool."""

    path: str = Field(description="Path to the saved screenshot")
    width: int = Field(description="Screenshot width in pixels")
    height: int = Field(description="Screenshot height in pixels")
    size_kb: float = Field(description="File size in KB")


class InteractionStep(BaseModel):
    """A single interaction to perform on a page."""

    action: str = Field(description="Action type: click, fill, select, wait, scroll")
    selector: str = Field(description="CSS selector for the target element")
    value: str | None = Field(default=None, description="Value for fill/select actions")


class CaptureFlowInput(BaseModel):
    """Input for the capture_flow tool."""

    url: str = Field(description="Starting URL")
    tag: str = Field(description="Doc tag for naming screenshots")
    steps: list[InteractionStep] = Field(description="Ordered interactions with captures between")
    capture_before_first: bool = Field(default=True, description="Capture a screenshot before the first interaction")


class CaptureFlowResult(BaseModel):
    """Result from the capture_flow tool."""

    screenshots: list[CaptureScreenshotResult] = Field(description="All captured screenshots in order")
    errors: list[str] = Field(default_factory=list, description="Errors during capture")
