"""Doc-writer MCP server definition and tool registration."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from octoauthor.mcp_servers.doc_writer import tools as tool_impl
from octoauthor.mcp_servers.doc_writer.config import DocWriterConfig


def create_doc_writer_server(config: DocWriterConfig | None = None) -> FastMCP:
    """Create and configure the doc-writer MCP server."""
    if config is None:
        config = DocWriterConfig()

    mcp = FastMCP(
        name="doc-writer-server",
        instructions="Documentation writer server. Generate and validate user documentation guides.",
    )

    def _get_provider():  # type: ignore[no-untyped-def]
        from octoauthor.core.providers import get_provider

        return get_provider("text")

    @mcp.tool()
    async def generate_guide(
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
    ) -> str:
        """Generate a complete documentation guide from page capture data.

        Args:
            tag: Doc tag in kebab-case (e.g., 'company-maintenance')
            title: Human-readable guide title
            route: App route this guide covers (e.g., '/companies')
            version: App version this doc targets
            applies_to: Products this doc applies to
            screenshots: Screenshot filenames to reference in steps
            dom_summary: Summary of the page DOM structure
            form_fields: Form field labels found on the page
            navigation_elements: Navigation/action elements found
            category: Doc category (admin, setup, features, etc.)
        """
        provider = _get_provider()
        result = await tool_impl.generate_guide(
            provider,
            config,
            tag=tag,
            title=title,
            route=route,
            version=version,
            applies_to=applies_to,
            screenshots=screenshots,
            dom_summary=dom_summary,
            form_fields=form_fields,
            navigation_elements=navigation_elements,
            category=category,
        )
        return json.dumps(result)

    @mcp.tool()
    async def rewrite_section(
        content_markdown: str,
        section_name: str,
        instructions: str,
    ) -> str:
        """Rewrite a specific section of a documentation guide.

        Args:
            content_markdown: Current full markdown content of the guide
            section_name: Section to rewrite (e.g., 'steps', 'overview', 'prerequisites')
            instructions: What to change (e.g., 'make step 3 clearer')
        """
        provider = _get_provider()
        result = await tool_impl.rewrite_section(
            provider, config, content_markdown, section_name, instructions
        )
        return json.dumps(result)

    @mcp.tool()
    def validate_content(content_markdown: str) -> str:
        """Validate documentation content against doc-standard rules.

        Args:
            content_markdown: Markdown content to validate
        """
        result = tool_impl.validate_content(content_markdown, config)
        return json.dumps(result)

    return mcp
