"""Capture models - structures for app navigation and screenshot capture."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class AuthStrategy(StrEnum):
    """Supported authentication strategies."""

    none = "none"
    storage_state = "storage_state"
    credentials = "credentials"


class AuthConfig(BaseModel):
    """Authentication configuration for accessing the target application."""

    strategy: AuthStrategy = Field(default=AuthStrategy.none, description="Auth strategy to use")
    storage_state_path: str | None = Field(
        default=None,
        description="Path to Playwright storage state JSON (cookies + localStorage)",
    )
    login_url: str | None = Field(default=None, description="Login page URL for credential-based auth")
    username_selector: str | None = Field(default=None, description="CSS selector for username field")
    password_selector: str | None = Field(default=None, description="CSS selector for password field")
    submit_selector: str | None = Field(default=None, description="CSS selector for login submit button")
    username: str | None = Field(default=None, description="Username (or use OCTOAUTHOR_AUTH_USERNAME env var)")
    password: str | None = Field(default=None, description="Password (or use OCTOAUTHOR_AUTH_PASSWORD env var)")
    wait_after_login: str | None = Field(
        default=None,
        description="CSS selector to wait for after login to confirm success",
    )


class RouteCapture(BaseModel):
    """Configuration for capturing a single route/screen."""

    route: str = Field(description="App route path (e.g., '/companies')")
    tag: str = Field(description="Doc tag this route maps to")
    title: str = Field(description="Human-readable screen title")
    wait_for: str | None = Field(default=None, description="CSS selector to wait for before capture")
    interactions: list[dict[str, str]] = Field(
        default_factory=list,
        description=(
            "Ordered interactions and screenshots. Each dict has one key: "
            "'click', 'fill' (selector|value), 'select' (selector|value), "
            "'wait' (selector), 'wait_hidden' (selector), or "
            "'screenshot' (description for the doc writer)."
        ),
    )


class CaptureConfig(BaseModel):
    """Top-level capture configuration for a target application."""

    app_name: str = Field(description="Name of the target application")
    base_url: HttpUrl = Field(description="Base URL of the running application")
    auth: AuthConfig = Field(default_factory=AuthConfig, description="Authentication config")
    viewport_width: int = Field(default=1280, description="Browser viewport width")
    viewport_height: int = Field(default=800, description="Browser viewport height")
    routes: list[RouteCapture] = Field(description="Routes to capture")
    light_mode_only: bool = Field(default=True, description="Force light mode for captures")


class CaptureResult(BaseModel):
    """Result from a capture session."""

    route: str = Field(description="Route that was captured")
    tag: str = Field(description="Doc tag for this capture")
    screenshots: list[str] = Field(description="Filenames of captured screenshots")
    screenshot_descriptions: list[str] = Field(
        default_factory=list,
        description="Human description of what each screenshot shows",
    )
    errors: list[str] = Field(default_factory=list, description="Any errors during capture")
