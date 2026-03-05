"""Doc-standard compliance checker — validates structure, metadata, formatting."""

from __future__ import annotations

import re
from typing import Any

import yaml

from octoauthor.core.security.models import FindingSeverity, ValidationFinding

_REQUIRED_METADATA = ["tag", "title", "version", "last_updated", "applies_to", "route", "generated_by"]
_TAG_PATTERN = re.compile(r"^[a-z][a-z0-9-]+$")
_VALID_CATEGORIES = {"admin", "setup", "features", "reports", "integrations", "general"}
_MAX_STEPS = 10
_MAX_WORDS = 1500
_FRONTMATTER_SEP = "---"


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith(_FRONTMATTER_SEP):
        return {}, content
    parts = content.split(_FRONTMATTER_SEP, 2)
    if len(parts) < 3:
        return {}, content
    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip("\n")
    return meta, body


def scan(content: str, filepath: str = "") -> list[ValidationFinding]:
    """Validate a doc file against the doc-standard spec."""
    findings: list[ValidationFinding] = []
    meta, body = _parse_frontmatter(content)

    # Metadata checks
    if not meta:
        findings.append(
            ValidationFinding(
                severity=FindingSeverity.HIGH,
                category="doc-standard",
                message="Missing YAML frontmatter",
                location=filepath,
            )
        )
        return findings

    for field in _REQUIRED_METADATA:
        if field not in meta:
            findings.append(
                ValidationFinding(
                    severity=FindingSeverity.HIGH,
                    category="doc-standard",
                    message=f"Missing required metadata field: {field}",
                    location=filepath,
                )
            )

    # Tag format
    tag = meta.get("tag", "")
    if tag and not _TAG_PATTERN.match(tag):
        findings.append(
            ValidationFinding(
                severity=FindingSeverity.MEDIUM,
                category="doc-standard",
                message=f"Tag format invalid (must be kebab-case): {tag}",
                location=filepath,
                evidence=tag,
            )
        )

    # Category
    category = meta.get("category", "general")
    if category not in _VALID_CATEGORIES:
        findings.append(
            ValidationFinding(
                severity=FindingSeverity.LOW,
                category="doc-standard",
                message=f"Unknown category: {category}",
                location=filepath,
            )
        )

    # Step count
    steps = re.findall(r"^\d+\.", body, re.MULTILINE)
    if len(steps) > _MAX_STEPS:
        findings.append(
            ValidationFinding(
                severity=FindingSeverity.MEDIUM,
                category="doc-standard",
                message=f"Too many steps: {len(steps)} (max {_MAX_STEPS})",
                location=filepath,
            )
        )

    # Word count
    word_count = len(body.split())
    if word_count > _MAX_WORDS:
        findings.append(
            ValidationFinding(
                severity=FindingSeverity.LOW,
                category="doc-standard",
                message=f"Word count {word_count} exceeds max {_MAX_WORDS}",
                location=filepath,
            )
        )

    return findings
