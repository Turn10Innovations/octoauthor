"""PII scanner — detects personal identifiable information patterns."""

from __future__ import annotations

import re

from octoauthor.core.security.models import FindingSeverity, ValidationFinding

# PII detection patterns
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_API_KEY_RE = re.compile(r"\b(?:sk-|pk_|ghp_|gho_|glpat-|xox[bsap]-)[A-Za-z0-9_-]{20,}\b")
_AWS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_SECRET_RE = re.compile(r"(?i)\b(?:password|secret|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]")

_PII_PATTERNS: list[tuple[re.Pattern[str], str, FindingSeverity]] = [
    (_EMAIL_RE, "Email address detected", FindingSeverity.HIGH),
    (_PHONE_RE, "Phone number detected", FindingSeverity.HIGH),
    (_SSN_RE, "Possible SSN detected", FindingSeverity.CRITICAL),
    (_API_KEY_RE, "API key/token detected", FindingSeverity.CRITICAL),
    (_AWS_KEY_RE, "AWS access key detected", FindingSeverity.CRITICAL),
    (_SECRET_RE, "Hardcoded secret detected", FindingSeverity.CRITICAL),
]

# Patterns to exclude (common false positives in documentation)
_EXCLUSIONS = [
    re.compile(r"example\.com"),
    re.compile(r"user@example"),
    re.compile(r"noreply@"),
    re.compile(r"demo@"),
    re.compile(r"test@"),
    re.compile(r"placeholder"),
]


def scan(content: str, filepath: str = "") -> list[ValidationFinding]:
    """Scan content for PII patterns."""
    findings: list[ValidationFinding] = []
    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern, message, severity in _PII_PATTERNS:
            for match in pattern.finditer(line):
                evidence = match.group()
                # Check exclusions
                if any(exc.search(evidence) for exc in _EXCLUSIONS):
                    continue
                findings.append(
                    ValidationFinding(
                        severity=severity,
                        category="pii",
                        message=message,
                        location=filepath,
                        line_number=line_num,
                        evidence=evidence[:100],
                    )
                )
    return findings
