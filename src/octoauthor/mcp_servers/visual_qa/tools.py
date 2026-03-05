"""Tool implementations for visual-qa MCP server."""

from __future__ import annotations

from pathlib import Path

from octoauthor.core.logging import get_logger
from octoauthor.mcp_servers.visual_qa import comparator, ocr
from octoauthor.mcp_servers.visual_qa.config import VisualQAConfig  # noqa: TC001
from octoauthor.mcp_servers.visual_qa.models import CheckAnnotationsResult

logger = get_logger(__name__)


def validate_screenshot(path: str, config: VisualQAConfig) -> dict:
    """Validate a screenshot meets spec requirements."""
    result = comparator.validate_screenshot(path, config)
    logger.info(
        "Screenshot validated",
        extra={"path": path, "passed": result.passed, "issue_count": len(result.issues)},
    )
    return result.model_dump()


def compare_screenshots(
    path_a: str,
    path_b: str,
    config: VisualQAConfig,
    save_diff: bool = False,
) -> dict:
    """Compare two screenshots for visual differences."""
    result = comparator.compare_screenshots(path_a, path_b, config, save_diff)
    logger.info(
        "Screenshots compared",
        extra={
            "path_a": path_a,
            "path_b": path_b,
            "identical": result.identical,
            "diff_pct": result.diff_percentage,
        },
    )
    return result.model_dump()


def scan_pii_visual(path: str) -> dict:
    """Scan a screenshot for visible PII using OCR."""
    result = ocr.scan_pii_visual(path)
    logger.info(
        "Visual PII scan complete",
        extra={"path": path, "pii_count": len(result.pii_found)},
    )
    return result.model_dump()


def check_annotations(path: str) -> dict:
    """Check annotation consistency in a screenshot.

    Detects numbered callouts, arrows, and highlight boxes by looking for
    specific color patterns (red/orange annotations are common).
    """
    from PIL import Image

    file_path = Path(path)
    if not file_path.exists():
        return CheckAnnotationsResult(
            path=path, has_annotations=False, issues=[f"File not found: {path}"]
        ).model_dump()

    img = Image.open(file_path).convert("RGB")
    pixels = list(img.get_flattened_data())
    width, height = img.size
    img.close()

    # Detect annotation-like colors (bright red, orange, yellow highlights)
    # These are common annotation colors: red (#FF0000-ish), orange (#FF6600-ish)
    annotation_pixels = 0
    for r, g, b in pixels:
        # Bright red or orange annotation colors
        if (r > 200 and g < 80 and b < 80) or (r > 200 and 80 < g < 150 and b < 80):
            annotation_pixels += 1

    total_pixels = len(pixels)
    annotation_ratio = annotation_pixels / total_pixels if total_pixels > 0 else 0

    # Heuristic: if more than 0.1% of pixels are annotation-colored
    has_annotations = annotation_ratio > 0.001
    # Rough estimate: each annotation callout is ~500 pixels
    estimated_count = max(1, annotation_pixels // 500) if has_annotations else 0

    issues: list[str] = []
    if has_annotations and annotation_ratio > 0.05:
        issues.append("Excessive annotations detected (>5% of image)")

    return CheckAnnotationsResult(
        path=path,
        has_annotations=has_annotations,
        annotation_count=estimated_count,
        issues=issues,
    ).model_dump()
