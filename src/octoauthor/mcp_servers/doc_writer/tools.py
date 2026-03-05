"""Tool implementations for the doc-writer MCP server."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from octoauthor.core.logging import get_logger
from octoauthor.mcp_servers.doc_writer.models import (
    GenerateGuideInput,
    GenerateGuideResult,
    RewriteSectionInput,
    RewriteSectionResult,
    ValidateContentResult,
)
from octoauthor.mcp_servers.doc_writer.prompts import (
    SYSTEM_PROMPT,
    build_generate_prompt,
    build_rewrite_prompt,
)

if TYPE_CHECKING:
    from octoauthor.core.providers.base import BaseProvider
    from octoauthor.mcp_servers.doc_writer.config import DocWriterConfig

logger = get_logger(__name__)


async def generate_guide(
    provider: BaseProvider,
    config: DocWriterConfig,
    tag: str,
    title: str,
    route: str,
    version: str,
    applies_to: list[str],
    screenshots: list[str] | None = None,
    dom_summary: str = "",
    form_fields: list[str] | None = None,
    navigation_elements: list[str] | None = None,
    category: str = "general",
) -> dict[str, Any]:
    """Generate a documentation guide using the LLM provider."""
    input_data = GenerateGuideInput(
        tag=tag,
        title=title,
        route=route,
        version=version,
        applies_to=applies_to,
        screenshots=screenshots or [],
        dom_summary=dom_summary,
        form_fields=form_fields or [],
        navigation_elements=navigation_elements or [],
        category=category,
    )

    system = SYSTEM_PROMPT.format(max_steps=config.max_steps_per_guide)
    prompt = build_generate_prompt(input_data)

    response = await provider.generate(prompt, system=system)

    content = response.text.strip()
    word_count = len(content.split())
    step_count = len(re.findall(r"^\d+\.", content, re.MULTILINE))

    result = GenerateGuideResult(
        tag=tag,
        title=title,
        content_markdown=content,
        step_count=step_count,
        word_count=word_count,
        provider_used=response.provider,
        model_used=response.model,
    )
    return result.model_dump()


async def rewrite_section(
    provider: BaseProvider,
    config: DocWriterConfig,
    content_markdown: str,
    section_name: str,
    instructions: str,
) -> dict[str, Any]:
    """Rewrite a specific section of a guide."""
    input_data = RewriteSectionInput(
        content_markdown=content_markdown,
        section_name=section_name,
        instructions=instructions,
    )

    system = SYSTEM_PROMPT.format(max_steps=config.max_steps_per_guide)
    prompt = build_rewrite_prompt(input_data)

    response = await provider.generate(prompt, system=system)

    result = RewriteSectionResult(
        content_markdown=response.text.strip(),
        section_changed=section_name,
    )
    return result.model_dump()


def validate_content(content_markdown: str, config: DocWriterConfig) -> dict[str, Any]:
    """Validate content against basic doc-standard rules."""
    issues: list[str] = []

    # Check word count
    word_count = len(content_markdown.split())
    if word_count > config.max_guide_length_words:
        issues.append(f"Word count {word_count} exceeds max {config.max_guide_length_words}")

    # Check step count
    steps = re.findall(r"^\d+\.", content_markdown, re.MULTILINE)
    if len(steps) > config.max_steps_per_guide:
        issues.append(f"Step count {len(steps)} exceeds max {config.max_steps_per_guide}")

    # Check for prohibited content patterns
    prohibited = [
        (r"```", "Code blocks are not allowed in user documentation"),
        (r"\$\s", "Terminal commands are not allowed"),
        (r"(?i)\bcurl\b", "Terminal commands (curl) are not allowed"),
        (r"(?i)\bapi\s+endpoint", "API references are not allowed in user docs"),
        (r"(?i)\bdatabase\b", "Database references are not allowed in user docs"),
        (r"(?i)\btodo\b", "Placeholder text (TODO) is not allowed"),
        (r"(?i)\btbd\b", "Placeholder text (TBD) is not allowed"),
        (r"(?i)lorem ipsum", "Placeholder text (Lorem ipsum) is not allowed"),
    ]
    for pattern, message in prohibited:
        if re.search(pattern, content_markdown):
            issues.append(message)

    # Check voice (basic heuristic — flag "You should")
    if re.search(r"(?i)\byou should\b", content_markdown):
        issues.append("Use imperative voice: 'Click Save' not 'You should click Save'")

    result = ValidateContentResult(valid=len(issues) == 0, issues=issues)
    return result.model_dump()
