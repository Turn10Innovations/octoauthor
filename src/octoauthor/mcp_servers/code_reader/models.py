"""Core data models for the code-reader MCP server."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ActionClassification(StrEnum):
    """How safe a UI feature is to interact with during capture.

    - view: Read-only display (pages, panels, tabs). Safe to navigate and screenshot.
    - interact: Opens UI without side effects (modals, dropdowns, accordions). Safe to click.
    - mutate: Changes data (save, delete, create). Needs sandbox mode or skip.
    """

    view = "view"
    interact = "interact"
    mutate = "mutate"


class ApiEndpoint(BaseModel):
    """A discovered API call found in source code."""

    method: str
    """HTTP method: GET, POST, PUT, PATCH, DELETE."""
    path: str
    """API path, e.g. '/api/v1/companies/{id}'."""
    source_file: str
    source_line: int | None = None


class FormFieldInfo(BaseModel):
    """A form field extracted from JSX or template markup."""

    label: str
    field_type: str
    """Field type: text, select, checkbox, date, number, etc."""
    name: str | None = None
    required: bool = False
    options: list[str] | None = None
    """Available choices for select/radio fields."""


class ComponentFeature(BaseModel):
    """A UI component or feature discovered via static analysis."""

    name: str
    """Component name, e.g. 'CustomRefreshModal'."""
    file_path: str
    """Relative path to the source file."""
    classification: ActionClassification
    trigger: str | None = None
    """CSS selector or text that activates this component."""
    description: str | None = None
    api_endpoints: list[ApiEndpoint] = []
    form_fields: list[FormFieldInfo] = []
    children: list[ComponentFeature] = []
    warnings: list[str] = []


class PageFeature(BaseModel):
    """A route/page in the application discovered from the router config."""

    route: str
    """Route path, e.g. '/reports'."""
    component_name: str
    """Top-level component rendered at this route."""
    file_path: str
    title: str | None = None
    classification: ActionClassification = ActionClassification.view
    requires_auth: bool = False
    required_role: str | None = None
    components: list[ComponentFeature] = []
    """Child UI components discovered within this page."""
    api_endpoints: list[ApiEndpoint] = []
    """Page-level data fetching endpoints."""


class MockRouteSpec(BaseModel):
    """A mock route specification for sandboxed capture of mutating features."""

    url_pattern: str
    """Glob pattern for Playwright page.route matching."""
    method: str
    status: int = 200
    body: dict | list | str = {}
    source_feature: str
    """Name of the ComponentFeature this mock was derived from."""
