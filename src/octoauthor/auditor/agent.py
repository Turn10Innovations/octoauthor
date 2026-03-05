"""Audit orchestration — runs the full audit pipeline on a PR."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from octoauthor.auditor.github_client import GitHubClient
from octoauthor.auditor.models import PRFile  # noqa: TC001
from octoauthor.auditor.reporter import build_review_action, determine_verdict, generate_summary
from octoauthor.auditor.reviewer import review_content
from octoauthor.core.logging import get_logger
from octoauthor.core.models.agents import AuditFinding, AuditReport, AuditSeverity
from octoauthor.core.security.engine import validate_content
from octoauthor.core.security.models import FindingSeverity

logger = get_logger(__name__)

_SEVERITY_MAP: dict[FindingSeverity, AuditSeverity] = {
    FindingSeverity.CRITICAL: AuditSeverity.CRITICAL,
    FindingSeverity.HIGH: AuditSeverity.HIGH,
    FindingSeverity.MEDIUM: AuditSeverity.MEDIUM,
    FindingSeverity.LOW: AuditSeverity.LOW,
    FindingSeverity.INFO: AuditSeverity.INFO,
}


async def run_audit(
    repo: str,
    pr_number: int,
    github_token: str,
    *,
    post_review: bool = False,
    skip_llm: bool = False,
) -> AuditReport:
    """Run the full audit pipeline on a GitHub PR.

    Args:
        repo: GitHub repo (owner/name).
        pr_number: PR number.
        github_token: GitHub token for API access.
        post_review: Whether to post the review to GitHub.
        skip_llm: Skip LLM-powered review (faster, security-only).

    Returns:
        Complete AuditReport.
    """
    run_id = uuid.uuid4().hex[:12]
    client = GitHubClient(github_token)

    logger.info("Starting audit", extra={"repo": repo, "pr": pr_number, "run_id": run_id})

    # 1. Fetch PR data
    pr_info = await client.get_pr(repo, pr_number)
    logger.info(
        "PR fetched",
        extra={"pr": pr_number, "files": len(pr_info.files), "branch": pr_info.branch},
    )

    # 2. Classify files
    doc_files = [f for f in pr_info.files if _is_doc_file(f) and f.status != "removed"]
    screenshot_files = [f for f in pr_info.files if _is_screenshot(f) and f.status != "removed"]

    all_findings: list[AuditFinding] = []
    model_used = "security-scanners-only"

    # 3. Audit doc files
    for doc_file in doc_files:
        content = await client.fetch_file_content(repo, pr_info.branch, doc_file.filename)

        # 3a. Run security scanners
        scan_result = validate_content(content, doc_file.filename)
        for finding in scan_result.findings:
            all_findings.append(
                AuditFinding(
                    severity=_SEVERITY_MAP.get(finding.severity, AuditSeverity.INFO),
                    category=finding.category,
                    title=finding.message,
                    detail=f"Scanner: {finding.category}",
                    file_path=doc_file.filename,
                    line_number=finding.line_number,
                    evidence=finding.evidence,
                )
            )

        # 3b. LLM review
        if not skip_llm:
            try:
                llm_findings = await review_content(content, doc_file.filename)
                all_findings.extend(llm_findings)
                if llm_findings:
                    model_used = "audit-provider"
            except Exception:
                logger.warning(
                    "LLM review failed, continuing with scanner results",
                    exc_info=True,
                    extra={"file": doc_file.filename},
                )

    # 4. Audit screenshots (basic validation)
    for screenshot in screenshot_files:
        all_findings.append(
            AuditFinding(
                severity=AuditSeverity.INFO,
                category="visual-qa",
                title=f"Screenshot added: {screenshot.filename}",
                detail="Screenshot should be validated for PII and spec compliance.",
                file_path=screenshot.filename,
            )
        )

    # 5. Build report
    verdict = determine_verdict(all_findings)
    report = AuditReport(
        run_id=run_id,
        pr_number=pr_number,
        branch=pr_info.branch,
        timestamp=datetime.now(tz=UTC),
        model_used=model_used,
        findings=all_findings,
        verdict=verdict,
        summary="",
        files_reviewed=len(doc_files),
        screenshots_scanned=len(screenshot_files),
    )
    report.summary = generate_summary(report)

    logger.info(
        "Audit complete",
        extra={
            "run_id": run_id,
            "verdict": verdict,
            "findings": len(all_findings),
            "files_reviewed": len(doc_files),
        },
    )

    # 6. Post review if requested
    if post_review:
        action = build_review_action(report)
        await client.post_review(repo, pr_number, action)
        if action.labels:
            await client.add_labels(repo, pr_number, action.labels)

    return report


def _is_doc_file(f: PRFile) -> bool:
    """Check if a file is a documentation file."""
    return f.filename.endswith(".md") and not f.filename.startswith(".")


def _is_screenshot(f: PRFile) -> bool:
    """Check if a file is a screenshot."""
    return any(f.filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp"))
