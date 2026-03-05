"""HTML/markdown sanitizer — detects dangerous content in generated docs."""

from __future__ import annotations

import re

from octoauthor.core.security.models import FindingSeverity, ValidationFinding

# Patterns that should never appear in user documentation
_DANGEROUS_PATTERNS: list[tuple[str, str, FindingSeverity]] = [
    (r"<script\b", "Script tag detected", FindingSeverity.CRITICAL),
    (r"<iframe\b", "Iframe tag detected", FindingSeverity.CRITICAL),
    (r"<object\b", "Object tag detected", FindingSeverity.HIGH),
    (r"<embed\b", "Embed tag detected", FindingSeverity.HIGH),
    (r"<form\b", "Form tag detected", FindingSeverity.HIGH),
    (r"\bon\w+\s*=", "Inline event handler detected (e.g., onclick=)", FindingSeverity.CRITICAL),
    (r"javascript:", "JavaScript URI scheme detected", FindingSeverity.CRITICAL),
    (r"data:text/html", "Data URI with HTML detected", FindingSeverity.HIGH),
    (r"<style\b[^>]*>.*?expression\s*\(", "CSS expression() detected", FindingSeverity.HIGH),
]


def scan(content: str, filepath: str = "") -> list[ValidationFinding]:
    """Scan content for dangerous HTML/script patterns."""
    findings: list[ValidationFinding] = []
    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern, message, severity in _DANGEROUS_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(
                    ValidationFinding(
                        severity=severity,
                        category="sanitizer",
                        message=message,
                        location=filepath,
                        line_number=line_num,
                        evidence=line.strip()[:200],
                    )
                )
    return findings
