"""Agent models - structures for inter-agent communication and audit reports."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    """Defined agent roles in the OctoAuthor pipeline."""

    NAVIGATOR = "navigator"
    WRITER = "writer"
    GRAPHIC_DESIGNER = "graphic_designer"
    QA_REVIEWER = "qa_reviewer"
    ORCHESTRATOR = "orchestrator"
    AUDITOR = "auditor"


class AgentMessage(BaseModel):
    """Message passed between agents in the pipeline."""

    from_agent: AgentRole = Field(description="Agent that produced this message")
    to_agent: AgentRole | None = Field(default=None, description="Target agent (None = broadcast)")
    message_type: str = Field(description="Message type (e.g., 'capture_complete', 'review_request')")
    payload: dict = Field(default_factory=dict, description="Message payload (typed per message_type)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str = Field(description="Pipeline run ID for tracing")


class AuditSeverity(StrEnum):
    """Severity levels for audit findings."""

    CRITICAL = "critical"   # Auto-block PR, notify human immediately
    HIGH = "high"           # Block PR, require human review of specific finding
    MEDIUM = "medium"       # Flag on PR, human should review
    LOW = "low"             # Informational, noted in report
    INFO = "info"           # Observation, no action needed


class AuditFinding(BaseModel):
    """A single finding from the auditor agent."""

    severity: AuditSeverity
    category: str = Field(description="Finding category (e.g., 'xss', 'prompt_injection', 'pii_leak')")
    title: str = Field(description="Short description of the finding")
    detail: str = Field(description="Detailed explanation of what was found and why it's flagged")
    file_path: str = Field(description="File where the finding was detected")
    line_number: int | None = Field(default=None, description="Line number if applicable")
    evidence: str = Field(default="", description="The content that triggered the finding")
    recommendation: str = Field(default="", description="Suggested remediation")
    false_positive_likelihood: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Estimated probability this is a false positive (0.0-1.0)",
    )


class AuditReport(BaseModel):
    """Complete audit report for a documentation PR."""

    run_id: str = Field(description="Unique ID for this audit run")
    pr_number: int = Field(description="GitHub PR number being audited")
    branch: str = Field(description="Branch being audited")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_used: str = Field(description="Model that performed the audit (e.g., 'claude-sonnet-4-6')")
    findings: list[AuditFinding] = Field(default_factory=list)
    verdict: str = Field(description="Overall verdict: 'passed', 'flagged', or 'blocked'")
    summary: str = Field(description="Human-readable summary of the audit")
    files_reviewed: int = Field(default=0, description="Number of files reviewed")
    screenshots_scanned: int = Field(default=0, description="Number of screenshots scanned for PII")

    @property
    def has_critical(self) -> bool:
        return any(f.severity == AuditSeverity.CRITICAL for f in self.findings)

    @property
    def has_high(self) -> bool:
        return any(f.severity == AuditSeverity.HIGH for f in self.findings)
