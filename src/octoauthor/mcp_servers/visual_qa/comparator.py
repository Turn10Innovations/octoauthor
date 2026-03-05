"""Visual diff and screenshot validation logic."""

from __future__ import annotations

from pathlib import Path

from octoauthor.core.logging import get_logger
from octoauthor.mcp_servers.visual_qa.config import VisualQAConfig  # noqa: TC001
from octoauthor.mcp_servers.visual_qa.models import (
    CompareScreenshotsResult,
    ValidateScreenshotResult,
)

logger = get_logger(__name__)


def validate_screenshot(path: str, config: VisualQAConfig) -> ValidateScreenshotResult:
    """Validate a screenshot against expected specs."""
    from PIL import Image

    file_path = Path(path)
    issues: list[str] = []

    if not file_path.exists():
        return ValidateScreenshotResult(
            path=path, passed=False, issues=[f"File not found: {path}"]
        )

    # Check file size
    size_kb = file_path.stat().st_size / 1024
    if size_kb > config.max_file_size_kb:
        issues.append(f"File size {size_kb:.1f}KB exceeds max {config.max_file_size_kb}KB")

    # Check format
    suffix = file_path.suffix.lstrip(".").lower()
    if suffix not in config.allowed_formats:
        issues.append(f"Format '{suffix}' not in allowed formats: {config.allowed_formats}")

    # Open and check dimensions
    img = Image.open(file_path)
    width, height = img.size
    img_format = (img.format or suffix).lower()

    if width != config.expected_width:
        issues.append(f"Width {width}px != expected {config.expected_width}px")

    if height < config.expected_height:
        issues.append(f"Height {height}px < minimum {config.expected_height}px")

    # Check for EXIF data
    has_exif = False
    exif = img.getexif()
    if exif:
        has_exif = True
        issues.append("EXIF metadata present (should be stripped for privacy)")

    img.close()

    return ValidateScreenshotResult(
        path=path,
        passed=len(issues) == 0,
        width=width,
        height=height,
        format=img_format,
        size_kb=round(size_kb, 1),
        has_exif=has_exif,
        issues=issues,
    )


def compare_screenshots(
    path_a: str,
    path_b: str,
    config: VisualQAConfig,
    save_diff: bool = False,
) -> CompareScreenshotsResult:
    """Compare two screenshots and compute pixel difference."""
    from PIL import Image, ImageChops

    file_a = Path(path_a)
    file_b = Path(path_b)
    issues: list[str] = []

    if not file_a.exists():
        return CompareScreenshotsResult(
            path_a=path_a, path_b=path_b, identical=False, issues=[f"File A not found: {path_a}"]
        )
    if not file_b.exists():
        return CompareScreenshotsResult(
            path_a=path_a, path_b=path_b, identical=False, issues=[f"File B not found: {path_b}"]
        )

    img_a = Image.open(file_a).convert("RGB")
    img_b = Image.open(file_b).convert("RGB")

    # Check dimensions
    size_match = img_a.size == img_b.size
    if not size_match:
        issues.append(f"Size mismatch: {img_a.size} vs {img_b.size}")
        img_a.close()
        img_b.close()
        return CompareScreenshotsResult(
            path_a=path_a,
            path_b=path_b,
            identical=False,
            diff_percentage=100.0,
            size_match=False,
            issues=issues,
        )

    # Compute pixel difference
    diff = ImageChops.difference(img_a, img_b)
    diff_pixels = list(diff.get_flattened_data())
    total_pixels = len(diff_pixels)
    changed_pixels = sum(1 for px in diff_pixels if any(c > 10 for c in px))
    diff_percentage = (changed_pixels / total_pixels * 100) if total_pixels > 0 else 0.0

    identical = diff_percentage == 0.0

    if diff_percentage > config.diff_threshold * 100:
        issues.append(
            f"Visual difference {diff_percentage:.2f}% exceeds threshold "
            f"{config.diff_threshold * 100:.1f}%"
        )

    # Optionally save diff image
    diff_path = None
    if save_diff and not identical:
        diff_file = file_a.parent / f"{file_a.stem}_vs_{file_b.stem}_diff.png"
        diff.save(diff_file)
        diff_path = str(diff_file)

    img_a.close()
    img_b.close()
    diff.close()

    return CompareScreenshotsResult(
        path_a=path_a,
        path_b=path_b,
        identical=identical,
        diff_percentage=round(diff_percentage, 2),
        size_match=size_match,
        diff_path=diff_path,
        issues=issues,
    )
