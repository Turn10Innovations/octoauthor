"""Capture models - structures for app navigation and screenshot capture."""

from pydantic import BaseModel, Field, HttpUrl


class RouteCapture(BaseModel):
    """Configuration for capturing a single route/screen."""

    route: str = Field(description="App route path (e.g., '/companies')")
    tag: str = Field(description="Doc tag this route maps to")
    title: str = Field(description="Human-readable screen title")
    wait_for: str | None = Field(default=None, description="CSS selector to wait for before capture")
    interactions: list[dict[str, str]] = Field(
        default_factory=list,
        description="Ordered interactions to perform (e.g., [{'click': '#add-btn'}, {'fill': '#name', 'value': 'Demo'}])",
    )
    capture_states: list[str] = Field(
        default_factory=list,
        description="Named states to capture (e.g., ['empty', 'filled', 'submitted'])",
    )


class CaptureConfig(BaseModel):
    """Top-level capture configuration for a target application."""

    app_name: str = Field(description="Name of the target application")
    base_url: HttpUrl = Field(description="Base URL of the running application")
    auth: dict[str, str] | None = Field(default=None, description="Auth credentials (resolved from env vars)")
    viewport_width: int = Field(default=1280, description="Browser viewport width")
    viewport_height: int = Field(default=800, description="Browser viewport height")
    routes: list[RouteCapture] = Field(description="Routes to capture")
    demo_data_script: str | None = Field(default=None, description="Script to seed demo data before capture")
    light_mode_only: bool = Field(default=True, description="Force light mode for captures")


class CaptureResult(BaseModel):
    """Result from a capture session."""

    route: str = Field(description="Route that was captured")
    tag: str = Field(description="Doc tag for this capture")
    screenshots: list[str] = Field(description="Paths to captured screenshot files")
    dom_snapshot: dict | None = Field(default=None, description="Simplified DOM structure of the page")
    form_fields: list[dict[str, str]] = Field(
        default_factory=list,
        description="Discovered form fields with labels and types",
    )
    navigation_elements: list[dict[str, str]] = Field(
        default_factory=list,
        description="Discovered navigation/action elements",
    )
    errors: list[str] = Field(default_factory=list, description="Any errors during capture")
