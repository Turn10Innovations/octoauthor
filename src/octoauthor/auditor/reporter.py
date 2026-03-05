"""AuditReport generation and formatting."""

from __future__ import annotations

from octoauthor.auditor.models import ReviewAction, ReviewComment
from octoauthor.core.models.agents import AuditFinding, AuditReport, AuditSeverity


def determine_verdict(findings: list[AuditFinding]) -> str:
    """Determine the overall verdict based on findings."""
    if any(f.severity == AuditSeverity.CRITICAL for f in findings):
        return "blocked"
    if any(f.severity == AuditSeverity.HIGH for f in findings):
        return "flagged"
    return "passed"


def generate_summary(report: AuditReport) -> str:
    """Generate a human-readable summary of the audit."""
    severity_counts: dict[str, int] = {}
    for f in report.findings:
        severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1

    lines = [
        f"## Audit Report — PR #{report.pr_number}",
        "",
        f"**Verdict:** {report.verdict.upper()}",
        f"**Files reviewed:** {report.files_reviewed}",
        f"**Screenshots scanned:** {report.screenshots_scanned}",
        f"**Model:** {report.model_used}",
        "",
    ]

    if report.findings:
        lines.append(f"### Findings ({len(report.findings)})")
        lines.append("")
        for sev in ["critical", "high", "medium", "low", "info"]:
            count = severity_counts.get(sev, 0)
            if count > 0:
                lines.append(f"- **{sev.upper()}**: {count}")
        lines.append("")

        for i, f in enumerate(report.findings, 1):
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(
                f.severity.value, "⚪"
            )
            lines.append(f"{emoji} **{i}. [{f.severity.value.upper()}] {f.title}**")
            lines.append(f"   - File: `{f.file_path}`")
            if f.detail:
                lines.append(f"   - {f.detail}")
            if f.recommendation:
                lines.append(f"   - Fix: {f.recommendation}")
            lines.append("")
    else:
        lines.append("No findings. All checks passed.")

    return "\n".join(lines)


def build_review_action(report: AuditReport) -> ReviewAction:
    """Build a GitHub review action from an audit report."""
    summary = generate_summary(report)

    if report.verdict == "blocked":
        event = "REQUEST_CHANGES"
        labels = ["audit:blocked"]
    elif report.verdict == "flagged":
        event = "REQUEST_CHANGES"
        labels = ["audit:flagged"]
    else:
        event = "APPROVE"
        labels = ["audit:passed"]

    # Build inline comments for critical/high findings
    comments: list[ReviewComment] = []
    for f in report.findings:
        if f.severity in (AuditSeverity.CRITICAL, AuditSeverity.HIGH):
            body = f"**[{f.severity.value.upper()}] {f.title}**\n\n{f.detail}"
            if f.recommendation:
                body += f"\n\n**Recommendation:** {f.recommendation}"
            comments.append(
                ReviewComment(
                    path=f.file_path,
                    line=f.line_number,
                    body=body,
                )
            )

    return ReviewAction(
        event=event,
        body=summary,
        comments=comments,
        labels=labels,
    )
