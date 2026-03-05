"""Screenshot capture and post-processing."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from octoauthor.core.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.async_api import Page

    from octoauthor.mcp_servers.screenshot.config import ScreenshotConfig
    from octoauthor.mcp_servers.screenshot.models import CaptureScreenshotResult

logger = get_logger(__name__)


def _strip_exif(png_bytes: bytes) -> bytes:
    """Strip EXIF/metadata from a PNG image using Pillow."""
    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes))
    clean = io.BytesIO()
    img.save(clean, format="PNG", optimize=True)
    return clean.getvalue()


async def capture_page(
    page: Page,
    output_path: Path,
    config: ScreenshotConfig,
    *,
    wait_for: str | None = None,
    full_page: bool = False,
) -> CaptureScreenshotResult:
    """Capture a screenshot of the current page state.

    Args:
        page: The Playwright page to capture.
        output_path: Where to save the screenshot.
        config: Screenshot server config.
        wait_for: Optional CSS selector to wait for before capture.
        full_page: Whether to capture the full scrollable page.

    Returns:
        CaptureScreenshotResult with path and dimensions.
    """
    from octoauthor.mcp_servers.screenshot.models import CaptureScreenshotResult as Result

    if wait_for:
        await page.wait_for_selector(wait_for, timeout=config.navigation_timeout_ms)

    # Small delay for rendering
    await page.wait_for_timeout(config.wait_after_load_ms)

    # Capture
    raw_bytes = await page.screenshot(full_page=full_page, type="png")

    # Post-processing
    if config.strip_exif:
        raw_bytes = _strip_exif(raw_bytes)

    # Validate size
    size_kb = len(raw_bytes) / 1024
    if size_kb > config.max_screenshot_size_kb:
        logger.warning(
            "Screenshot exceeds size limit",
            extra={
                "size_kb": round(size_kb, 1),
                "limit_kb": config.max_screenshot_size_kb,
            },
        )

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(raw_bytes)

    return Result(
        path=str(output_path),
        width=config.viewport_width,
        height=config.viewport_height if not full_page else 0,
        size_kb=round(size_kb, 2),
    )
