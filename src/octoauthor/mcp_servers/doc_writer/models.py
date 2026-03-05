"""Pydantic models for doc-writer MCP server inputs/outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateGuideInput(BaseModel):
    """Input for the generate_guide tool."""

    tag: str = Field(description="Doc tag (kebab-case)")
    title: str = Field(description="Guide title")
    route: str = Field(description="App route this guide covers")
    version: str = Field(description="App version")
    applies_to: list[str] = Field(description="Products this applies to")
    screenshots: list[str] = Field(default_factory=list, description="Screenshot filenames in order")
    screenshot_descriptions: list[str] = Field(default_factory=list, description="What each screenshot shows")
    dom_summary: str = Field(default="", description="Summary of the page DOM structure")
    form_fields: list[str] = Field(default_factory=list, description="Form field labels found on page")
    navigation_elements: list[str] = Field(default_factory=list, description="Navigation/action elements found")
    category: str = Field(default="general", description="Doc category")


class GenerateGuideResult(BaseModel):
    """Result from the generate_guide tool."""

    tag: str
    title: str
    content_markdown: str = Field(description="Generated markdown content")
    step_count: int = Field(description="Number of steps in the guide")
    word_count: int = Field(description="Total word count")
    screenshot_count: int = Field(default=0, description="Number of screenshots referenced")
    provider_used: str = Field(description="Provider that generated the content")
    model_used: str = Field(description="Model that generated the content")


class RewriteSectionInput(BaseModel):
    """Input for the rewrite_section tool."""

    content_markdown: str = Field(description="Current full markdown content")
    section_name: str = Field(description="Section to rewrite (e.g., 'steps', 'overview')")
    instructions: str = Field(description="Rewrite instructions (e.g., 'make step 3 clearer')")


class RewriteSectionResult(BaseModel):
    """Result from the rewrite_section tool."""

    content_markdown: str = Field(description="Updated markdown content")
    section_changed: str = Field(description="Which section was changed")


class ValidateContentResult(BaseModel):
    """Result from the validate_content tool."""

    valid: bool = Field(description="Whether the content passes all checks")
    issues: list[str] = Field(default_factory=list, description="List of validation issues found")
