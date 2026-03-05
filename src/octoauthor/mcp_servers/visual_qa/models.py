"""Pydantic models for visual-qa MCP server inputs/outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidateScreenshotResult(BaseModel):
    """Result from validating a screenshot against specs."""

    path: str = Field(description="Path to the screenshot")
    passed: bool = Field(description="Whether the screenshot passes all checks")
    width: int = Field(default=0, description="Actual width")
    height: int = Field(default=0, description="Actual height")
    format: str = Field(default="", description="Image format")
    size_kb: float = Field(default=0.0, description="File size in KB")
    has_exif: bool = Field(default=False, description="Whether EXIF data was found")
    issues: list[str] = Field(default_factory=list, description="List of validation issues")


class CompareScreenshotsResult(BaseModel):
    """Result from comparing two screenshots."""

    path_a: str = Field(description="Path to screenshot A")
    path_b: str = Field(description="Path to screenshot B")
    identical: bool = Field(description="Whether the images are identical")
    diff_percentage: float = Field(
        default=0.0,
        description="Percentage of pixels that differ (0-100)",
    )
    size_match: bool = Field(default=True, description="Whether dimensions match")
    diff_path: str | None = Field(default=None, description="Path to diff image if generated")
    issues: list[str] = Field(default_factory=list, description="Comparison issues")


class PIIFinding(BaseModel):
    """A PII finding in a screenshot via OCR."""

    text: str = Field(description="The detected text")
    pii_type: str = Field(description="Type of PII (email, phone, ssn, etc.)")
    confidence: float = Field(default=1.0, description="Detection confidence (0-1)")
    region: str = Field(default="", description="Approximate region in the image")


class ScanPIIVisualResult(BaseModel):
    """Result from OCR-based PII scanning of a screenshot."""

    path: str = Field(description="Path to the screenshot")
    pii_found: list[PIIFinding] = Field(description="PII findings")
    text_extracted: bool = Field(description="Whether text extraction succeeded")
    error: str | None = Field(default=None, description="Error message if OCR failed")


class CheckAnnotationsResult(BaseModel):
    """Result from checking annotation consistency."""

    path: str = Field(description="Path to the screenshot")
    has_annotations: bool = Field(description="Whether annotations were detected")
    annotation_count: int = Field(default=0, description="Number of annotations found")
    issues: list[str] = Field(default_factory=list, description="Annotation issues")
