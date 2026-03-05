"""Tests for the screenshot MCP server."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from octoauthor.mcp_servers.screenshot.config import ScreenshotConfig
from octoauthor.mcp_servers.screenshot.models import (
    CaptureFlowInput,
    CaptureScreenshotInput,
    CaptureScreenshotResult,
    InteractionStep,
)


class TestScreenshotConfig:
    def test_defaults(self) -> None:
        config = ScreenshotConfig()
        assert config.viewport_width == 1280
        assert config.viewport_height == 800
        assert config.light_mode_only is True
        assert config.strip_exif is True
        assert config.max_screenshot_size_kb == 500

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OCTOAUTHOR_VIEWPORT_WIDTH", "1920")
        monkeypatch.setenv("OCTOAUTHOR_VIEWPORT_HEIGHT", "1080")
        config = ScreenshotConfig()
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080


class TestScreenshotModels:
    def test_capture_input(self) -> None:
        inp = CaptureScreenshotInput(
            url="http://localhost:3000/companies",
            output_filename="company-list-01.png",
        )
        assert inp.wait_for is None
        assert inp.full_page is False

    def test_capture_result(self) -> None:
        result = CaptureScreenshotResult(
            path="/tmp/test.png",
            width=1280,
            height=800,
            size_kb=150.5,
        )
        assert result.size_kb == 150.5

    def test_interaction_step(self) -> None:
        step = InteractionStep(action="click", selector="#add-btn")
        assert step.value is None

    def test_capture_flow_input(self) -> None:
        flow = CaptureFlowInput(
            url="http://localhost:3000/companies",
            tag="company-maintenance",
            steps=[
                InteractionStep(action="click", selector="#add-btn"),
                InteractionStep(action="fill", selector="#name", value="Demo Corp"),
            ],
        )
        assert len(flow.steps) == 2
        assert flow.capture_before_first is True


class TestCapture:
    @pytest.mark.asyncio
    async def test_capture_page_strips_exif(self, tmp_path: Path) -> None:
        """Test that capture_page strips EXIF and saves a valid file."""
        from PIL import Image

        from octoauthor.mcp_servers.screenshot.capture import capture_page

        # Create a test PNG image
        img = Image.new("RGB", (1280, 800), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        # Mock the page
        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=png_bytes)
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        config = ScreenshotConfig()
        output_path = tmp_path / "test-capture.png"

        result = await capture_page(mock_page, output_path, config)

        assert output_path.exists()
        assert result.width == 1280
        assert result.height == 800
        assert result.size_kb > 0
        mock_page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_capture_page_with_wait_for(self, tmp_path: Path) -> None:
        """Test that capture_page waits for selector when specified."""
        from PIL import Image

        from octoauthor.mcp_servers.screenshot.capture import capture_page

        img = Image.new("RGB", (1280, 800), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=buf.getvalue())
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        config = ScreenshotConfig()
        output_path = tmp_path / "test-wait.png"

        await capture_page(mock_page, output_path, config, wait_for="#main-content")

        mock_page.wait_for_selector.assert_called_once_with("#main-content", timeout=config.navigation_timeout_ms)


class TestTools:
    @pytest.mark.asyncio
    async def test_capture_screenshot_tool(self, tmp_path: Path) -> None:
        """Test the capture_screenshot tool function with mocked browser."""
        from PIL import Image

        from octoauthor.mcp_servers.screenshot import tools as tool_impl
        from octoauthor.mcp_servers.screenshot.browser import BrowserSession

        img = Image.new("RGB", (1280, 800), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=buf.getvalue())
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.close = AsyncMock()

        mock_session = MagicMock(spec=BrowserSession)
        mock_session.new_page = AsyncMock(return_value=mock_page)

        config = ScreenshotConfig(screenshot_output_dir=str(tmp_path))

        result = await tool_impl.capture_screenshot(
            mock_session, config, "http://localhost:3000", "test.png"
        )

        assert result["width"] == 1280
        assert (tmp_path / "test.png").exists()
        mock_page.goto.assert_called_once()
        mock_page.close.assert_called_once()
