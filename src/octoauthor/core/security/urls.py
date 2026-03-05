"""URL checker — validates URLs against an allowlist."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from octoauthor.core.security.models import FindingSeverity, ValidationFinding

_URL_PATTERN = re.compile(r"https?://[^\s\)\"'>]+")


def scan(content: str, filepath: str = "", allowlist: list[str] | None = None) -> list[ValidationFinding]:
    """Scan content for URLs and check against allowlist.

    Args:
        content: Markdown content to scan.
        filepath: Source file path for reporting.
        allowlist: Allowed domain patterns. If empty/None, all URLs are flagged as info.
    """
    findings: list[ValidationFinding] = []
    allowed = allowlist or []

    for line_num, line in enumerate(content.splitlines(), 1):
        for match in _URL_PATTERN.finditer(line):
            url = match.group()
            parsed = urlparse(url)
            domain = parsed.netloc

            if allowed and not any(domain.endswith(a) for a in allowed):
                findings.append(
                    ValidationFinding(
                        severity=FindingSeverity.MEDIUM,
                        category="urls",
                        message=f"URL domain not in allowlist: {domain}",
                        location=filepath,
                        line_number=line_num,
                        evidence=url[:200],
                    )
                )
    return findings
