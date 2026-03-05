"""Unicode scanner — detects invisible characters, homoglyphs, RTL overrides."""

from __future__ import annotations

import re

from octoauthor.core.security.models import FindingSeverity, ValidationFinding

# Invisible/zero-width characters
_INVISIBLE_CHARS = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
    r"\u2060\u2061\u2062\u2063\u2064\u2066\u2067\u2068\u2069\ufeff\ufffe]"
)

# RTL override characters (can be used to disguise text direction)
_RTL_OVERRIDES = re.compile(r"[\u202d\u202e\u2066\u2067\u2068\u2069]")


def scan(content: str, filepath: str = "") -> list[ValidationFinding]:
    """Scan content for suspicious Unicode characters."""
    findings: list[ValidationFinding] = []
    for line_num, line in enumerate(content.splitlines(), 1):
        for match in _INVISIBLE_CHARS.finditer(line):
            char_code = f"U+{ord(match.group()):04X}"
            findings.append(
                ValidationFinding(
                    severity=FindingSeverity.HIGH,
                    category="unicode",
                    message=f"Invisible Unicode character detected: {char_code}",
                    location=filepath,
                    line_number=line_num,
                    evidence=f"character at position {match.start()}",
                )
            )
        for match in _RTL_OVERRIDES.finditer(line):
            char_code = f"U+{ord(match.group()):04X}"
            findings.append(
                ValidationFinding(
                    severity=FindingSeverity.CRITICAL,
                    category="unicode",
                    message=f"RTL override character detected: {char_code}",
                    location=filepath,
                    line_number=line_num,
                    evidence=f"character at position {match.start()}",
                )
            )
    return findings
