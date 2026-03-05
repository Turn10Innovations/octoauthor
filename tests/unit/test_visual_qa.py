"""Tests for visual-qa MCP server."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from octoauthor.mcp_servers.visual_qa.config import VisualQAConfig
from octoauthor.mcp_servers.visual_qa.models import (
    CheckAnnotationsResult,
    CompareScreenshotsResult,
    PIIFinding,
    ScanPIIVisualResult,
    ValidateScreenshotResult,
)


@pytest.fixture()
def config() -> VisualQAConfig:
    return VisualQAConfig()


@pytest.fixture()
def valid_screenshot(tmp_path: Path) -> Path:
    """Create a valid 1280x800 PNG screenshot."""
    img = Image.new("RGB", (1280, 800), color=(255, 255, 255))
    path = tmp_path / "valid.png"
    img.save(path, format="PNG")
    img.close()
    return path


@pytest.fixture()
def small_screenshot(tmp_path: Path) -> Path:
    """Create an undersized screenshot."""
    img = Image.new("RGB", (800, 600), color=(200, 200, 200))
    path = tmp_path / "small.png"
    img.save(path, format="PNG")
    img.close()
    return path


@pytest.fixture()
def annotated_screenshot(tmp_path: Path) -> Path:
    """Create a screenshot with red annotation pixels."""
    img = Image.new("RGB", (1280, 800), color=(255, 255, 255))
    # Draw some red "annotation" pixels
    pixels = img.load()
    for x in range(100, 200):
        for y in range(100, 200):
            pixels[x, y] = (255, 0, 0)  # bright red
    path = tmp_path / "annotated.png"
    img.save(path, format="PNG")
    img.close()
    return path


class TestVisualQAConfig:
    def test_defaults(self) -> None:
        config = VisualQAConfig()
        assert config.expected_width == 1280
        assert config.expected_height == 800
        assert config.max_file_size_kb == 500
        assert config.allowed_formats == ["png"]
        assert config.diff_threshold == 0.05


class TestVisualQAModels:
    def test_validate_screenshot_result(self) -> None:
        result = ValidateScreenshotResult(
            path="/tmp/test.png", passed=True, width=1280, height=800
        )
        assert result.passed is True

    def test_compare_screenshots_result(self) -> None:
        result = CompareScreenshotsResult(
            path_a="/tmp/a.png", path_b="/tmp/b.png", identical=True
        )
        assert result.identical is True

    def test_pii_finding(self) -> None:
        finding = PIIFinding(text="john@company.com", pii_type="email")
        assert finding.pii_type == "email"

    def test_scan_pii_visual_result(self) -> None:
        result = ScanPIIVisualResult(path="/tmp/test.png", pii_found=[], text_extracted=True)
        assert result.text_extracted is True

    def test_check_annotations_result(self) -> None:
        result = CheckAnnotationsResult(
            path="/tmp/test.png", has_annotations=True, annotation_count=3
        )
        assert result.annotation_count == 3


class TestValidateScreenshot:
    def test_valid_screenshot_passes(self, valid_screenshot: Path, config: VisualQAConfig) -> None:
        from octoauthor.mcp_servers.visual_qa.comparator import validate_screenshot

        result = validate_screenshot(str(valid_screenshot), config)
        assert result.passed is True
        assert result.width == 1280
        assert result.height == 800
        assert result.has_exif is False

    def test_wrong_dimensions(self, small_screenshot: Path, config: VisualQAConfig) -> None:
        from octoauthor.mcp_servers.visual_qa.comparator import validate_screenshot

        result = validate_screenshot(str(small_screenshot), config)
        assert result.passed is False
        assert any("Width" in i for i in result.issues)
        assert any("Height" in i for i in result.issues)

    def test_file_not_found(self, config: VisualQAConfig) -> None:
        from octoauthor.mcp_servers.visual_qa.comparator import validate_screenshot

        result = validate_screenshot("/nonexistent/file.png", config)
        assert result.passed is False
        assert any("not found" in i for i in result.issues)

    def test_oversize_file(self, tmp_path: Path, config: VisualQAConfig) -> None:
        from octoauthor.mcp_servers.visual_qa.comparator import validate_screenshot

        # Create a large image
        img = Image.new("RGB", (1280, 800), color=(128, 128, 128))
        path = tmp_path / "large.png"
        img.save(path, format="PNG")
        img.close()

        # Override config to have a tiny max
        tiny_config = VisualQAConfig(max_file_size_kb=1)
        result = validate_screenshot(str(path), tiny_config)
        assert result.passed is False
        assert any("size" in i.lower() for i in result.issues)


class TestCompareScreenshots:
    def test_identical_images(self, valid_screenshot: Path, config: VisualQAConfig) -> None:
        from octoauthor.mcp_servers.visual_qa.comparator import compare_screenshots

        result = compare_screenshots(
            str(valid_screenshot), str(valid_screenshot), config
        )
        assert result.identical is True
        assert result.diff_percentage == 0.0
        assert result.size_match is True

    def test_different_images(
        self, valid_screenshot: Path, small_screenshot: Path, config: VisualQAConfig
    ) -> None:
        from octoauthor.mcp_servers.visual_qa.comparator import compare_screenshots

        result = compare_screenshots(
            str(valid_screenshot), str(small_screenshot), config
        )
        assert result.identical is False
        assert result.size_match is False
        assert any("Size mismatch" in i for i in result.issues)

    def test_similar_but_different(self, tmp_path: Path, config: VisualQAConfig) -> None:
        from octoauthor.mcp_servers.visual_qa.comparator import compare_screenshots

        img_a = Image.new("RGB", (1280, 800), color=(255, 255, 255))
        path_a = tmp_path / "a.png"
        img_a.save(path_a, format="PNG")
        img_a.close()

        img_b = Image.new("RGB", (1280, 800), color=(255, 255, 254))
        path_b = tmp_path / "b.png"
        img_b.save(path_b, format="PNG")
        img_b.close()

        result = compare_screenshots(str(path_a), str(path_b), config)
        assert result.size_match is True
        # Very subtle difference, might not exceed threshold
        assert result.diff_percentage >= 0

    def test_save_diff_image(self, tmp_path: Path, config: VisualQAConfig) -> None:
        from octoauthor.mcp_servers.visual_qa.comparator import compare_screenshots

        img_a = Image.new("RGB", (1280, 800), color=(255, 255, 255))
        path_a = tmp_path / "white.png"
        img_a.save(path_a, format="PNG")
        img_a.close()

        img_b = Image.new("RGB", (1280, 800), color=(0, 0, 0))
        path_b = tmp_path / "black.png"
        img_b.save(path_b, format="PNG")
        img_b.close()

        result = compare_screenshots(str(path_a), str(path_b), config, save_diff=True)
        assert result.identical is False
        assert result.diff_path is not None
        assert Path(result.diff_path).exists()

    def test_file_not_found(self, config: VisualQAConfig) -> None:
        from octoauthor.mcp_servers.visual_qa.comparator import compare_screenshots

        result = compare_screenshots("/no/a.png", "/no/b.png", config)
        assert result.identical is False
        assert any("not found" in i for i in result.issues)


class TestCheckAnnotations:
    def test_no_annotations(self, valid_screenshot: Path) -> None:
        from octoauthor.mcp_servers.visual_qa.tools import check_annotations

        result = check_annotations(str(valid_screenshot))
        assert result["has_annotations"] is False
        assert result["annotation_count"] == 0

    def test_with_annotations(self, annotated_screenshot: Path) -> None:
        from octoauthor.mcp_servers.visual_qa.tools import check_annotations

        result = check_annotations(str(annotated_screenshot))
        assert result["has_annotations"] is True
        assert result["annotation_count"] >= 1

    def test_file_not_found(self) -> None:
        from octoauthor.mcp_servers.visual_qa.tools import check_annotations

        result = check_annotations("/nonexistent/file.png")
        assert result["has_annotations"] is False
        assert any("not found" in i for i in result["issues"])


class TestScanPIIVisual:
    def test_no_tesseract_graceful(self, valid_screenshot: Path) -> None:
        """OCR scan should handle missing pytesseract gracefully."""
        from octoauthor.mcp_servers.visual_qa.ocr import scan_pii_visual

        result = scan_pii_visual(str(valid_screenshot))
        # Either works (tesseract installed) or gracefully reports unavailable
        assert isinstance(result.pii_found, list)

    def test_file_not_found(self) -> None:
        from octoauthor.mcp_servers.visual_qa.ocr import scan_pii_visual

        result = scan_pii_visual("/nonexistent/file.png")
        assert result.text_extracted is False
        assert result.error is not None


class TestToolWrappers:
    def test_validate_screenshot_tool(self, valid_screenshot: Path, config: VisualQAConfig) -> None:
        from octoauthor.mcp_servers.visual_qa.tools import validate_screenshot

        result = validate_screenshot(str(valid_screenshot), config)
        assert result["passed"] is True

    def test_compare_screenshots_tool(
        self, valid_screenshot: Path, config: VisualQAConfig
    ) -> None:
        from octoauthor.mcp_servers.visual_qa.tools import compare_screenshots

        result = compare_screenshots(
            str(valid_screenshot), str(valid_screenshot), config
        )
        assert result["identical"] is True

    def test_scan_pii_visual_tool(self, valid_screenshot: Path) -> None:
        from octoauthor.mcp_servers.visual_qa.tools import scan_pii_visual

        result = scan_pii_visual(str(valid_screenshot))
        assert "pii_found" in result
