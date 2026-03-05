"""Validation engine — composes all security scanners."""

from __future__ import annotations

from octoauthor.core.logging import get_logger
from octoauthor.core.security import content, pii, sanitizer, unicode, urls, validator
from octoauthor.core.security.models import ValidationFinding, ValidationResult

logger = get_logger(__name__)


def validate_content(
    content_text: str,
    filepath: str = "",
    *,
    url_allowlist: list[str] | None = None,
    skip_scanners: set[str] | None = None,
) -> ValidationResult:
    """Run all security scanners on content.

    Args:
        content_text: The markdown content to validate.
        filepath: Source file path for reporting.
        url_allowlist: Allowed URL domains.
        skip_scanners: Scanner names to skip.

    Returns:
        ValidationResult with aggregated findings.
    """
    skip = skip_scanners or set()
    all_findings: list[ValidationFinding] = []
    scanners_run: list[str] = []

    scanners = [
        ("sanitizer", lambda: sanitizer.scan(content_text, filepath)),
        ("unicode", lambda: unicode.scan(content_text, filepath)),
        ("pii", lambda: pii.scan(content_text, filepath)),
        ("content", lambda: content.scan(content_text, filepath)),
        ("urls", lambda: urls.scan(content_text, filepath, url_allowlist)),
        ("doc-standard", lambda: validator.scan(content_text, filepath)),
    ]

    for name, scanner_fn in scanners:
        if name in skip:
            continue
        scanners_run.append(name)
        findings = scanner_fn()
        all_findings.extend(findings)

    passed = len(all_findings) == 0
    return ValidationResult(
        passed=passed,
        findings=all_findings,
        scanners_run=scanners_run,
        files_checked=1,
    )
