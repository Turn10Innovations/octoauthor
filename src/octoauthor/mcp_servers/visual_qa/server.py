"""Visual QA MCP server definition and tool registration."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from octoauthor.mcp_servers.visual_qa import tools as tool_impl
from octoauthor.mcp_servers.visual_qa.config import VisualQAConfig


def create_visual_qa_server(
    config: VisualQAConfig | None = None,
    **mcp_kwargs: Any,
) -> FastMCP:
    """Create and configure the visual-qa MCP server."""
    if config is None:
        config = VisualQAConfig()

    mcp = FastMCP(
        name="visual-qa-server",
        instructions="Visual QA server. Validates screenshots, compares images, scans for PII, checks annotations.",
        **mcp_kwargs,
    )

    @mcp.tool()
    def validate_screenshot(path: str) -> str:
        """Validate a screenshot meets documentation spec requirements.

        Checks: dimensions, file size, format, EXIF metadata.

        Args:
            path: Absolute path to the screenshot file
        """
        result = tool_impl.validate_screenshot(path, config)
        return json.dumps(result)

    @mcp.tool()
    def compare_screenshots(
        path_a: str,
        path_b: str,
        save_diff: bool = False,
    ) -> str:
        """Compare two screenshots for visual differences.

        Args:
            path_a: Path to the first screenshot
            path_b: Path to the second screenshot
            save_diff: Whether to save a diff image
        """
        result = tool_impl.compare_screenshots(path_a, path_b, config, save_diff)
        return json.dumps(result)

    @mcp.tool()
    def scan_pii_visual(path: str) -> str:
        """Scan a screenshot for visible PII using OCR.

        Detects emails, phone numbers, SSNs, and API keys visible in screenshots.
        Requires pytesseract to be installed for OCR.

        Args:
            path: Absolute path to the screenshot file
        """
        result = tool_impl.scan_pii_visual(path)
        return json.dumps(result)

    @mcp.tool()
    def check_annotations(path: str) -> str:
        """Check annotation consistency in a screenshot.

        Detects numbered callouts, arrows, and highlight boxes.

        Args:
            path: Absolute path to the screenshot file
        """
        result = tool_impl.check_annotations(path)
        return json.dumps(result)

    return mcp
