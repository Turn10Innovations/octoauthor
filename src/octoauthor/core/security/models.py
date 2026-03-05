"""Security validation models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FindingSeverity(StrEnum):
    """Severity levels for security findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ValidationFinding(BaseModel):
    """A single finding from a security scanner or validator."""

    severity: FindingSeverity
    category: str = Field(description="Scanner category (e.g., 'pii', 'sanitizer', 'doc-standard')")
    message: str = Field(description="Human-readable description of the finding")
    location: str = Field(default="", description="File path or section where found")
    line_number: int | None = Field(default=None, description="Line number if applicable")
    evidence: str = Field(default="", description="The content that triggered the finding")


class ValidationResult(BaseModel):
    """Result from a validation run (one or more scanners)."""

    passed: bool = Field(description="Whether all checks passed")
    findings: list[ValidationFinding] = Field(default_factory=list)
    scanners_run: list[str] = Field(default_factory=list, description="Which scanners were executed")
    files_checked: int = Field(default=0)
