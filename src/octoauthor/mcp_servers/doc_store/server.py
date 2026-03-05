"""Doc-store MCP server definition and tool registration."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from octoauthor.mcp_servers.doc_store import tools as tool_impl
from octoauthor.mcp_servers.doc_store.config import DocStoreConfig
from octoauthor.mcp_servers.doc_store.storage import DocStorage


def create_doc_store_server(config: DocStoreConfig | None = None) -> FastMCP:
    """Create and configure the doc-store MCP server."""
    if config is None:
        config = DocStoreConfig()

    storage = DocStorage(
        doc_dir=config.doc_output_dir,
        screenshot_dir=config.screenshot_output_dir,
        manifest_filename=config.manifest_filename,
    )

    mcp = FastMCP(
        name="doc-store-server",
        instructions="Document storage server. Store, retrieve, list, and delete documentation files and screenshots.",
    )

    @mcp.tool()
    def store_doc(
        tag: str,
        title: str,
        version: str,
        applies_to: list[str],
        route: str,
        content_markdown: str,
        category: str = "general",
    ) -> str:
        """Store a documentation file with YAML frontmatter and update the manifest.

        Args:
            tag: Unique doc tag in kebab-case (e.g., 'company-maintenance')
            title: Human-readable title for the doc
            version: App version this doc targets
            applies_to: List of products this doc applies to
            route: App route this doc covers (e.g., '/companies')
            content_markdown: Full markdown content of the guide
            category: Doc category (admin, setup, features, reports, integrations, general)
        """
        result = tool_impl.store_doc(storage, tag, title, version, applies_to, route, content_markdown, category)
        return json.dumps(result)

    @mcp.tool()
    def get_doc(tag: str) -> str:
        """Retrieve a stored doc by its tag.

        Args:
            tag: The doc tag to retrieve (e.g., 'company-maintenance')
        """
        result = tool_impl.get_doc(storage, tag)
        if result is None:
            return json.dumps({"error": f"Doc not found: {tag}"})
        return json.dumps(result)

    @mcp.tool()
    def list_docs() -> str:
        """List all stored documentation files with their metadata."""
        result = tool_impl.list_docs(storage)
        return json.dumps(result)

    @mcp.tool()
    def delete_doc(tag: str) -> str:
        """Delete a doc and its associated screenshots by tag.

        Args:
            tag: The doc tag to delete
        """
        result = tool_impl.delete_doc(storage, tag)
        return json.dumps(result)

    @mcp.tool()
    def store_screenshot(
        tag: str,
        filename: str,
        data_base64: str,
        alt_text: str = "",
        step_number: int | None = None,
    ) -> str:
        """Store a screenshot file from base64-encoded PNG data.

        Args:
            tag: Doc tag this screenshot belongs to
            filename: Screenshot filename (e.g., 'company-list-01.png')
            data_base64: Base64-encoded PNG image data
            alt_text: Accessibility alt text for the screenshot
            step_number: Step number this screenshot illustrates
        """
        result = tool_impl.store_screenshot(storage, tag, filename, data_base64, alt_text, step_number)
        return json.dumps(result)

    @mcp.tool()
    def get_manifest() -> str:
        """Return the full manifest index of all stored docs."""
        result = tool_impl.get_manifest(storage)
        return json.dumps(result)

    return mcp
