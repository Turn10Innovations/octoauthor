"""Tests for Pydantic model validation."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from octoauthor.core.models.agents import (
    AgentMessage,
    AgentRole,
    AuditFinding,
    AuditReport,
    AuditSeverity,
)
from octoauthor.core.models.capture import CaptureConfig, CaptureResult, RouteCapture
from octoauthor.core.models.docs import DocBundle, DocMetadata, DocStep, Screenshot
from octoauthor.core.models.providers import ProviderConfig, ProvidersConfig, ProviderType
from octoauthor.core.models.service import DiscoveryResponse, MCPServerInfo


class TestScreenshot:
    def test_defaults(self) -> None:
        s = Screenshot(filename="test.png", path="/tmp/test.png", route="/home")
        assert s.width == 1280
        assert s.height == 800
        assert s.alt_text == ""
        assert s.annotations == []

    def test_with_step(self) -> None:
        s = Screenshot(
            filename="step-01.png",
            path="/tmp/step-01.png",
            route="/companies",
            step_number=1,
            alt_text="Company list page",
        )
        assert s.step_number == 1
        assert s.alt_text == "Company list page"


class TestDocStep:
    def test_minimal(self) -> None:
        step = DocStep(number=1, instruction="Click **Add Company**")
        assert step.number == 1
        assert step.screenshot is None
        assert step.substeps == []

    def test_with_screenshot(self) -> None:
        ss = Screenshot(filename="s.png", path="/tmp/s.png", route="/")
        step = DocStep(number=1, instruction="Click Save", screenshot=ss)
        assert step.screenshot is not None


class TestDocMetadata:
    def test_required_fields(self) -> None:
        meta = DocMetadata(
            tag="company-maintenance",
            title="Company Management",
            version="1.0.0",
            last_updated=date(2026, 3, 5),
            applies_to=["octohub-core"],
            route="/companies",
        )
        assert meta.tag == "company-maintenance"
        assert meta.generated_by == "octoauthor"

    def test_missing_required_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocMetadata(tag="x", title="X")  # type: ignore[call-arg]


class TestDocBundle:
    def test_complete_bundle(self) -> None:
        meta = DocMetadata(
            tag="test",
            title="Test Guide",
            version="1.0",
            last_updated=date.today(),
            applies_to=["app"],
            route="/test",
        )
        bundle = DocBundle(
            metadata=meta,
            content_markdown="# Test Guide\n\nOverview.",
            steps=[DocStep(number=1, instruction="Do something")],
        )
        assert bundle.checksum == ""
        assert len(bundle.steps) == 1


class TestProviderConfig:
    def test_defaults(self) -> None:
        config = ProviderConfig(provider=ProviderType.OLLAMA, model="qwen3:32b")
        assert config.max_tokens == 4096
        assert config.temperature == 0.3
        assert config.supports_vision is False

    def test_temperature_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ProviderConfig(provider=ProviderType.OLLAMA, model="x", temperature=3.0)

    def test_all_provider_types(self) -> None:
        for pt in ProviderType:
            config = ProviderConfig(provider=pt, model="test")
            assert config.provider == pt


class TestProvidersConfig:
    def test_text_only(self) -> None:
        text = ProviderConfig(provider=ProviderType.OLLAMA, model="qwen3:32b")
        config = ProvidersConfig(text=text)
        assert config.vision is None
        assert config.audit is None


class TestRouteCapture:
    def test_minimal(self) -> None:
        rc = RouteCapture(route="/companies", tag="company-maint", title="Companies")
        assert rc.interactions == []
        assert rc.capture_states == []


class TestCaptureConfig:
    def test_full_config(self) -> None:
        config = CaptureConfig(
            app_name="TestApp",
            base_url="http://localhost:3000",
            routes=[
                RouteCapture(route="/home", tag="home", title="Home"),
            ],
        )
        assert config.viewport_width == 1280
        assert config.light_mode_only is True


class TestCaptureResult:
    def test_minimal(self) -> None:
        result = CaptureResult(
            route="/companies",
            tag="company-maint",
            screenshots=["/tmp/s1.png"],
        )
        assert result.errors == []
        assert result.form_fields == []


class TestAgentModels:
    def test_agent_message(self) -> None:
        msg = AgentMessage(
            from_agent=AgentRole.NAVIGATOR,
            message_type="capture_complete",
            correlation_id="run-123",
        )
        assert msg.to_agent is None
        assert isinstance(msg.timestamp, datetime)

    def test_audit_finding(self) -> None:
        finding = AuditFinding(
            severity=AuditSeverity.HIGH,
            category="pii_leak",
            title="Email address found",
            detail="Found email in step 3",
            file_path="docs/guide.md",
        )
        assert finding.false_positive_likelihood == 0.0

    def test_audit_report_properties(self) -> None:
        critical_finding = AuditFinding(
            severity=AuditSeverity.CRITICAL,
            category="xss",
            title="XSS",
            detail="Script tag",
            file_path="test.md",
        )
        report = AuditReport(
            run_id="audit-1",
            pr_number=42,
            branch="openclaw/test",
            model_used="claude-sonnet-4-6",
            findings=[critical_finding],
            verdict="blocked",
            summary="Blocked due to XSS",
        )
        assert report.has_critical is True
        assert report.has_high is False


class TestServiceModels:
    def test_mcp_server_info(self) -> None:
        info = MCPServerInfo(
            name="doc-store-server",
            url="http://localhost:8102/mcp",
            description="Document storage",
            tools=["store_doc", "get_doc"],
        )
        assert info.transport == "sse"

    def test_discovery_response(self) -> None:
        resp = DiscoveryResponse(
            version="0.1.0",
            mcp_servers=[
                MCPServerInfo(
                    name="test",
                    url="http://localhost:8100/mcp",
                )
            ],
            playbooks=[],
            specs={"doc_standard": "http://localhost:8000/api/v1/specs/doc-standard"},
        )
        assert resp.service == "octoauthor"
        assert resp.health == "ok"
