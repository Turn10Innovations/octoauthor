"""OCR-based PII detection in screenshots."""

from __future__ import annotations

import re
from pathlib import Path

from octoauthor.core.logging import get_logger
from octoauthor.mcp_servers.visual_qa.models import PIIFinding, ScanPIIVisualResult

logger = get_logger(__name__)

# PII patterns to look for in extracted text
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_API_KEY_RE = re.compile(r"\b(?:sk-|pk_|ghp_|gho_|glpat-|xox[bsap]-)[A-Za-z0-9_-]{20,}\b")

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (_EMAIL_RE, "email"),
    (_PHONE_RE, "phone"),
    (_SSN_RE, "ssn"),
    (_API_KEY_RE, "api_key"),
]

# Common false-positive exclusions
_EXCLUSIONS = [
    re.compile(r"example\.com"),
    re.compile(r"user@example"),
    re.compile(r"noreply@"),
    re.compile(r"demo@"),
    re.compile(r"test@"),
]


def _extract_text_from_image(path: str) -> str | None:
    """Extract text from an image using basic OCR.

    Uses pytesseract if available, otherwise returns None.
    """
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        img.close()
        return text
    except ImportError:
        logger.debug("pytesseract not installed, OCR unavailable")
        return None
    except Exception:
        logger.warning("OCR extraction failed", exc_info=True, extra={"path": path})
        return None


def scan_pii_visual(path: str) -> ScanPIIVisualResult:
    """Scan a screenshot for visible PII using OCR."""
    file_path = Path(path)
    if not file_path.exists():
        return ScanPIIVisualResult(
            path=path,
            pii_found=[],
            text_extracted=False,
            error=f"File not found: {path}",
        )

    text = _extract_text_from_image(path)
    if text is None:
        return ScanPIIVisualResult(
            path=path,
            pii_found=[],
            text_extracted=False,
            error="OCR not available (pytesseract not installed)",
        )

    findings: list[PIIFinding] = []
    for pattern, pii_type in _PII_PATTERNS:
        for match in pattern.finditer(text):
            evidence = match.group()
            if any(exc.search(evidence) for exc in _EXCLUSIONS):
                continue
            findings.append(
                PIIFinding(
                    text=evidence[:50],
                    pii_type=pii_type,
                )
            )

    return ScanPIIVisualResult(
        path=path,
        pii_found=findings,
        text_extracted=True,
    )
