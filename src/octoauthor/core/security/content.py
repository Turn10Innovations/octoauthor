"""Content checker — validates against doc-standard prohibited content rules."""

from __future__ import annotations

import re

from octoauthor.core.security.models import FindingSeverity, ValidationFinding

_PROHIBITED: list[tuple[str, str]] = [
    (r"```", "Code blocks are not allowed in user documentation"),
    (r"(?i)\bcurl\s", "Terminal commands (curl) not allowed"),
    (r"(?i)\bpip\s+install\b", "Terminal commands (pip install) not allowed"),
    (r"(?i)\bnpm\s+install\b", "Terminal commands (npm install) not allowed"),
    (r"(?i)\bgit\s+(?:clone|push|pull)\b", "Terminal commands (git) not allowed"),
    (r"(?i)\bsudo\b", "Terminal commands (sudo) not allowed"),
    (r"(?i)\bapi\s+endpoint", "API references not allowed in user docs"),
    (r"(?i)\bdatabase\s+(?:table|schema|migration)", "Database references not allowed"),
    (r"(?i)\btodo\b", "Placeholder text (TODO) not allowed"),
    (r"(?i)\btbd\b", "Placeholder text (TBD) not allowed"),
    (r"(?i)lorem ipsum", "Placeholder text not allowed"),
    (r"(?i)\byou should\b", "Use imperative voice (not 'you should')"),
    (r"(?i)\bthe user should\b", "Use imperative voice (not 'the user should')"),
]


def scan(content: str, filepath: str = "") -> list[ValidationFinding]:
    """Scan content for prohibited patterns from doc-standard."""
    findings: list[ValidationFinding] = []
    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern, message in _PROHIBITED:
            if re.search(pattern, line):
                findings.append(
                    ValidationFinding(
                        severity=FindingSeverity.MEDIUM,
                        category="content",
                        message=message,
                        location=filepath,
                        line_number=line_num,
                        evidence=line.strip()[:200],
                    )
                )
    return findings
