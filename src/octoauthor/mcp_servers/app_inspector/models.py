"""Pydantic models for app-inspector MCP server inputs/outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DOMElement(BaseModel):
    """A simplified DOM element representation."""

    tag: str = Field(description="HTML tag name")
    id: str | None = Field(default=None, description="Element id attribute")
    classes: list[str] = Field(default_factory=list, description="CSS class names")
    text: str = Field(default="", description="Visible text content (truncated)")
    role: str | None = Field(default=None, description="ARIA role")
    href: str | None = Field(default=None, description="Link href if applicable")
    children_count: int = Field(default=0, description="Number of child elements")


class InspectPageResult(BaseModel):
    """Result from inspecting a page's DOM structure."""

    url: str = Field(description="URL that was inspected")
    title: str = Field(description="Page title")
    heading: str | None = Field(default=None, description="Main heading (h1) text")
    landmark_count: int = Field(default=0, description="Number of ARIA landmarks")
    elements: list[DOMElement] = Field(description="Key semantic elements found")
    meta: dict[str, str] = Field(default_factory=dict, description="Page meta tags")


class RouteInfo(BaseModel):
    """A discovered route/link."""

    href: str = Field(description="Link URL or path")
    text: str = Field(description="Link text")
    is_internal: bool = Field(default=True, description="Whether the link is internal")
    source_selector: str = Field(default="", description="CSS selector of the link element")


class DiscoverRoutesResult(BaseModel):
    """Result from route discovery."""

    base_url: str = Field(description="Base URL used for internal/external classification")
    routes: list[RouteInfo] = Field(description="Discovered routes")
    total_links: int = Field(default=0, description="Total links found on page")


class FormFieldInfo(BaseModel):
    """A discovered form field."""

    name: str = Field(default="", description="Field name attribute")
    field_type: str = Field(description="Input type (text, email, select, etc.)")
    label: str = Field(default="", description="Associated label text")
    required: bool = Field(default=False, description="Whether the field is required")
    placeholder: str = Field(default="", description="Placeholder text")
    selector: str = Field(default="", description="CSS selector for the field")


class FormInfo(BaseModel):
    """A discovered form."""

    action: str = Field(default="", description="Form action URL")
    method: str = Field(default="GET", description="Form method")
    fields: list[FormFieldInfo] = Field(description="Form fields")
    submit_label: str = Field(default="", description="Submit button text")


class DiscoverFormsResult(BaseModel):
    """Result from form discovery."""

    url: str = Field(description="URL that was inspected")
    forms: list[FormInfo] = Field(description="Discovered forms")


class ActionElement(BaseModel):
    """A discovered interactive element."""

    element_type: str = Field(description="Element type: button, link, dropdown, toggle, etc.")
    text: str = Field(description="Visible text or aria-label")
    selector: str = Field(description="CSS selector for the element")
    is_primary: bool = Field(default=False, description="Whether it appears to be a primary action")


class DiscoverActionsResult(BaseModel):
    """Result from action discovery."""

    url: str = Field(description="URL that was inspected")
    actions: list[ActionElement] = Field(description="Discovered interactive elements")
