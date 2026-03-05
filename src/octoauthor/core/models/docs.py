"""Documentation models - the core data structures for generated docs."""

from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field


class Screenshot(BaseModel):
    """A captured screenshot with metadata."""

    filename: str = Field(description="Screenshot filename (e.g., 'company-list.png')")
    path: Path = Field(description="Local path to the screenshot file")
    route: str = Field(description="App route where screenshot was taken")
    width: int = Field(default=1280, description="Screenshot width in pixels")
    height: int = Field(default=800, description="Screenshot height in pixels")
    step_number: int | None = Field(default=None, description="Step number in the guide flow")
    alt_text: str = Field(default="", description="Accessibility alt text")
    annotations: list[str] = Field(default_factory=list, description="Visual annotation descriptions")


class DocStep(BaseModel):
    """A single step in a user guide."""

    number: int = Field(description="Step number (1-indexed)")
    instruction: str = Field(description="Imperative instruction (e.g., 'Click Add Company')")
    description: str = Field(default="", description="Additional context for this step")
    screenshot: Screenshot | None = Field(default=None, description="Screenshot for this step")
    ui_element: str | None = Field(default=None, description="CSS selector or element identifier")
    substeps: list[str] = Field(default_factory=list, description="Optional sub-steps")


class DocMetadata(BaseModel):
    """Metadata for a documentation page. Stored in frontmatter."""

    tag: str = Field(description="Unique tag linking doc to app screen (e.g., 'company-maintenance')")
    title: str = Field(description="Human-readable title")
    version: str = Field(description="App version this doc was generated for")
    last_updated: date = Field(description="Date of last generation/update")
    applies_to: list[str] = Field(description="Which products this applies to (e.g., ['octohub-core'])")
    route: str = Field(description="App route this doc covers (e.g., '/companies')")
    category: str = Field(default="general", description="Doc category (e.g., 'admin', 'setup', 'features')")
    prerequisites: list[str] = Field(default_factory=list, description="Tags of docs that should be read first")
    related: list[str] = Field(default_factory=list, description="Tags of related docs")
    generated_by: str = Field(default="octoauthor", description="Tool that generated this doc")


class DocBundle(BaseModel):
    """A complete documentation bundle ready for storage."""

    metadata: DocMetadata
    content_markdown: str = Field(description="The full markdown content of the guide")
    steps: list[DocStep] = Field(default_factory=list, description="Structured steps (if step-by-step guide)")
    screenshots: list[Screenshot] = Field(default_factory=list, description="All screenshots in this doc")
    checksum: str = Field(default="", description="Content hash for change detection")
