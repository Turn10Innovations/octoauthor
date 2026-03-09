"""Tests for auditor module — agent, github_client, reviewer, reporter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from octoauthor.auditor.models import PRFile, PRInfo, ReviewAction, ReviewComment
from octoauthor.auditor.reporter import (
    build_review_action,
    determine_verdict,
    generate_summary,
)
from octoauthor.auditor.reviewer import _parse_review_response
from octoauthor.core.models.agents import AuditFinding, AuditReport, AuditSeverity


class TestAuditorModels:
    def test_pr_file(self) -> None:
        f = PRFile(filename="docs/guide.md", status="added", additions=10)
        assert f.status == "added"

    def test_pr_info(self) -> None:
        info = PRInfo(
            number=42,
            title="Add company guide",
            branch="octoauthor/doc-update",
            files=[PRFile(filename="docs/guide.md", status="added")],
        )
        assert info.number == 42
        assert len(info.files) == 1

    def test_review_comment(self) -> None:
        c = ReviewComment(path="docs/guide.md", line=5, body="PII detected")
        assert c.line == 5

    def test_review_action(self) -> None:
        action = ReviewAction(
            event="REQUEST_CHANGES",
            body="Issues found",
            labels=["audit:flagged"],
        )
        assert action.event == "REQUEST_CHANGES"


class TestReporter:
    @pytest.fixture()
    def clean_report(self) -> AuditReport:
        return AuditReport(
            run_id="abc123",
            pr_number=42,
            branch="feature/docs",
            model_used="test-model",
            findings=[],
            verdict="passed",
            summary="",
            files_reviewed=3,
            screenshots_scanned=1,
        )

    @pytest.fixture()
    def flagged_report(self) -> AuditReport:
        return AuditReport(
            run_id="def456",
            pr_number=42,
            branch="feature/docs",
            model_used="test-model",
            findings=[
                AuditFinding(
                    severity=AuditSeverity.HIGH,
                    category="pii",
                    title="Email address detected",
                    detail="Found email in guide",
                    file_path="docs/guide.md",
                    line_number=10,
                ),
                AuditFinding(
                    severity=AuditSeverity.MEDIUM,
                    category="content",
                    title="Wrong voice",
                    detail="Uses passive voice",
                    file_path="docs/guide.md",
                ),
            ],
            verdict="flagged",
            summary="",
        )

    @pytest.fixture()
    def blocked_report(self) -> AuditReport:
        return AuditReport(
            run_id="ghi789",
            pr_number=42,
            branch="feature/docs",
            model_used="test-model",
            findings=[
                AuditFinding(
                    severity=AuditSeverity.CRITICAL,
                    category="sanitizer",
                    title="XSS detected",
                    detail="Script tag found",
                    file_path="docs/guide.md",
                    recommendation="Remove script tag",
                ),
            ],
            verdict="blocked",
            summary="",
        )

    def test_determine_verdict_passed(self) -> None:
        assert determine_verdict([]) == "passed"

    def test_determine_verdict_flagged(self) -> None:
        findings = [
            AuditFinding(
                severity=AuditSeverity.HIGH,
                category="test",
                title="t",
                detail="d",
                file_path="f",
            )
        ]
        assert determine_verdict(findings) == "flagged"

    def test_determine_verdict_blocked(self) -> None:
        findings = [
            AuditFinding(
                severity=AuditSeverity.CRITICAL,
                category="test",
                title="t",
                detail="d",
                file_path="f",
            )
        ]
        assert determine_verdict(findings) == "blocked"

    def test_generate_summary_clean(self, clean_report: AuditReport) -> None:
        summary = generate_summary(clean_report)
        assert "PR #42" in summary
        assert "PASSED" in summary
        assert "No findings" in summary

    def test_generate_summary_with_findings(self, flagged_report: AuditReport) -> None:
        summary = generate_summary(flagged_report)
        assert "FLAGGED" in summary
        assert "HIGH" in summary
        assert "Email address detected" in summary

    def test_build_review_action_passed(self, clean_report: AuditReport) -> None:
        action = build_review_action(clean_report)
        assert action.event == "APPROVE"
        assert "audit:passed" in action.labels

    def test_build_review_action_flagged(self, flagged_report: AuditReport) -> None:
        action = build_review_action(flagged_report)
        assert action.event == "REQUEST_CHANGES"
        assert "audit:flagged" in action.labels
        # Should have inline comment for HIGH finding
        assert len(action.comments) == 1
        assert "Email" in action.comments[0].body

    def test_build_review_action_blocked(self, blocked_report: AuditReport) -> None:
        action = build_review_action(blocked_report)
        assert action.event == "REQUEST_CHANGES"
        assert "audit:blocked" in action.labels
        assert len(action.comments) == 1
        assert "XSS" in action.comments[0].body
        assert "Remove script tag" in action.comments[0].body


class TestReviewer:
    def test_parse_valid_response(self) -> None:
        response = json.dumps([
            {
                "severity": "high",
                "title": "Missing step",
                "detail": "Step 3 skips saving",
                "recommendation": "Add save step",
            }
        ])
        findings = _parse_review_response(response, "docs/guide.md", "test-model")
        assert len(findings) == 1
        assert findings[0].severity == AuditSeverity.HIGH
        assert findings[0].title == "Missing step"
        assert findings[0].category == "llm-review"

    def test_parse_empty_response(self) -> None:
        findings = _parse_review_response("[]", "docs/guide.md", "test-model")
        assert findings == []

    def test_parse_invalid_json(self) -> None:
        findings = _parse_review_response("not json", "docs/guide.md", "test-model")
        assert findings == []

    def test_parse_code_block_wrapped(self) -> None:
        response = "```json\n[]\n```"
        findings = _parse_review_response(response, "docs/guide.md", "test-model")
        assert findings == []

    def test_parse_unknown_severity(self) -> None:
        response = json.dumps([{"severity": "unknown", "title": "T", "detail": "D"}])
        findings = _parse_review_response(response, "f", "m")
        assert len(findings) == 1
        assert findings[0].severity == AuditSeverity.INFO

    def test_parse_non_list_response(self) -> None:
        findings = _parse_review_response('{"not": "a list"}', "f", "m")
        assert findings == []


class TestGitHubClient:
    @pytest.mark.asyncio()
    async def test_get_pr(self) -> None:
        from octoauthor.auditor.github_client import GitHubClient

        client = GitHubClient("fake-token")

        mock_pr_resp = MagicMock()
        mock_pr_resp.json.return_value = {
            "title": "Add docs",
            "head": {"ref": "feature/docs"},
            "base": {"ref": "main"},
            "user": {"login": "testuser"},
        }
        mock_pr_resp.raise_for_status = MagicMock()

        mock_files_resp = MagicMock()
        mock_files_resp.json.return_value = [
            {"filename": "docs/guide.md", "status": "added", "additions": 50, "deletions": 0, "patch": "+content"},
        ]
        mock_files_resp.raise_for_status = MagicMock()

        with patch("octoauthor.auditor.github_client.httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=[mock_pr_resp, mock_files_resp])
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            pr_info = await client.get_pr("owner/repo", 42)

        assert pr_info.number == 42
        assert pr_info.title == "Add docs"
        assert pr_info.branch == "feature/docs"
        assert len(pr_info.files) == 1

    @pytest.mark.asyncio()
    async def test_post_review(self) -> None:
        from octoauthor.auditor.github_client import GitHubClient

        client = GitHubClient("fake-token")
        action = ReviewAction(event="APPROVE", body="LGTM", labels=["audit:passed"])

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None

        with patch("octoauthor.auditor.github_client.httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            await client.post_review("owner/repo", 42, action)

        mock_http.post.assert_called_once()

    @pytest.mark.asyncio()
    async def test_add_labels(self) -> None:
        from octoauthor.auditor.github_client import GitHubClient

        client = GitHubClient("fake-token")

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None

        with patch("octoauthor.auditor.github_client.httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            await client.add_labels("owner/repo", 42, ["audit:passed"])

        mock_http.post.assert_called_once()

    @pytest.mark.asyncio()
    async def test_add_labels_empty_noop(self) -> None:
        from octoauthor.auditor.github_client import GitHubClient

        client = GitHubClient("fake-token")
        # Should not make any API calls
        await client.add_labels("owner/repo", 42, [])


class TestAuditAgent:
    @pytest.mark.asyncio()
    async def test_run_audit_clean_doc(self) -> None:
        from octoauthor.auditor.agent import run_audit

        clean_doc = (
            "---\ntag: test-doc\ntitle: Test\nversion: '1.0'\nlast_updated: '2026-03-05'\n"
            "applies_to: [app]\nroute: /test\ngenerated_by: octoauthor\ncategory: features\n---\n\n"
            "1. Click **Save**\n2. Enter the name"
        )

        mock_pr_info = PRInfo(
            number=42,
            title="Add docs",
            branch="feature/docs",
            files=[PRFile(filename="docs/guide.md", status="added")],
        )

        with (
            patch("octoauthor.auditor.agent.GitHubClient") as mock_gh_cls,
        ):
            mock_gh = AsyncMock()
            mock_gh.get_pr = AsyncMock(return_value=mock_pr_info)
            mock_gh.fetch_file_content = AsyncMock(return_value=clean_doc)
            mock_gh_cls.return_value = mock_gh

            report = await run_audit("owner/repo", 42, "fake-token", skip_llm=True)

        assert report.verdict == "passed"
        assert report.files_reviewed == 1
        assert report.pr_number == 42

    @pytest.mark.asyncio()
    async def test_run_audit_xss_blocked(self) -> None:
        from octoauthor.auditor.agent import run_audit

        xss_doc = (
            "---\ntag: test\ntitle: T\nversion: '1'\nlast_updated: '2026-01-01'\n"
            "applies_to: [a]\nroute: /t\ngenerated_by: octoauthor\n---\n\n"
            '<script>alert("xss")</script>'
        )

        mock_pr_info = PRInfo(
            number=99,
            title="Bad docs",
            branch="octoauthor/docs",
            files=[PRFile(filename="docs/bad.md", status="added")],
        )

        with patch("octoauthor.auditor.agent.GitHubClient") as mock_gh_cls:
            mock_gh = AsyncMock()
            mock_gh.get_pr = AsyncMock(return_value=mock_pr_info)
            mock_gh.fetch_file_content = AsyncMock(return_value=xss_doc)
            mock_gh_cls.return_value = mock_gh

            report = await run_audit("owner/repo", 99, "fake-token", skip_llm=True)

        assert report.verdict == "blocked"
        assert any(f.category == "sanitizer" for f in report.findings)

    @pytest.mark.asyncio()
    async def test_run_audit_with_screenshots(self) -> None:
        from octoauthor.auditor.agent import run_audit

        clean_doc = (
            "---\ntag: t\ntitle: T\nversion: '1'\nlast_updated: '2026-01-01'\n"
            "applies_to: [a]\nroute: /t\ngenerated_by: octoauthor\ncategory: features\n---\n\n"
            "1. Click **Save**"
        )

        mock_pr_info = PRInfo(
            number=42,
            title="Docs with screenshots",
            branch="feature/docs",
            files=[
                PRFile(filename="docs/guide.md", status="added"),
                PRFile(filename="docs/screenshots/step1.png", status="added"),
            ],
        )

        with patch("octoauthor.auditor.agent.GitHubClient") as mock_gh_cls:
            mock_gh = AsyncMock()
            mock_gh.get_pr = AsyncMock(return_value=mock_pr_info)
            mock_gh.fetch_file_content = AsyncMock(return_value=clean_doc)
            mock_gh_cls.return_value = mock_gh

            report = await run_audit("owner/repo", 42, "fake-token", skip_llm=True)

        assert report.screenshots_scanned == 1
        assert any(f.category == "visual-qa" for f in report.findings)

    @pytest.mark.asyncio()
    async def test_run_audit_posts_review(self) -> None:
        from octoauthor.auditor.agent import run_audit

        clean_doc = (
            "---\ntag: t\ntitle: T\nversion: '1'\nlast_updated: '2026-01-01'\n"
            "applies_to: [a]\nroute: /t\ngenerated_by: octoauthor\ncategory: features\n---\n\n"
            "1. Click **Save**"
        )

        mock_pr_info = PRInfo(
            number=42,
            title="Docs",
            branch="feature/docs",
            files=[PRFile(filename="docs/guide.md", status="added")],
        )

        with patch("octoauthor.auditor.agent.GitHubClient") as mock_gh_cls:
            mock_gh = AsyncMock()
            mock_gh.get_pr = AsyncMock(return_value=mock_pr_info)
            mock_gh.fetch_file_content = AsyncMock(return_value=clean_doc)
            mock_gh.post_review = AsyncMock()
            mock_gh.add_labels = AsyncMock()
            mock_gh_cls.return_value = mock_gh

            report = await run_audit(
                "owner/repo", 42, "fake-token", post_review=True, skip_llm=True
            )

        assert report.verdict == "passed"
        mock_gh.post_review.assert_called_once()
        mock_gh.add_labels.assert_called_once()

    @pytest.mark.asyncio()
    async def test_run_audit_ignores_removed_files(self) -> None:
        from octoauthor.auditor.agent import run_audit

        mock_pr_info = PRInfo(
            number=42,
            title="Remove docs",
            branch="cleanup",
            files=[PRFile(filename="docs/old.md", status="removed")],
        )

        with patch("octoauthor.auditor.agent.GitHubClient") as mock_gh_cls:
            mock_gh = AsyncMock()
            mock_gh.get_pr = AsyncMock(return_value=mock_pr_info)
            mock_gh_cls.return_value = mock_gh

            report = await run_audit("owner/repo", 42, "fake-token", skip_llm=True)

        assert report.files_reviewed == 0
        mock_gh.fetch_file_content.assert_not_called()
