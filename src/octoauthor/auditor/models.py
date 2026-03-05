"""Auditor-specific models for PR data and review actions."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PRFile(BaseModel):
    """A file from a GitHub PR diff."""

    filename: str = Field(description="File path relative to repo root")
    status: str = Field(description="File status: added, modified, removed, renamed")
    additions: int = Field(default=0, description="Lines added")
    deletions: int = Field(default=0, description="Lines deleted")
    patch: str = Field(default="", description="Unified diff patch")
    content: str = Field(default="", description="Full file content (if fetchable)")


class PRInfo(BaseModel):
    """Metadata about a GitHub pull request."""

    number: int = Field(description="PR number")
    title: str = Field(description="PR title")
    branch: str = Field(description="Head branch name")
    base_branch: str = Field(default="main", description="Base branch name")
    author: str = Field(default="", description="PR author login")
    files: list[PRFile] = Field(default_factory=list, description="Changed files")


class ReviewComment(BaseModel):
    """A comment to post on a specific file/line in a PR review."""

    path: str = Field(description="File path")
    line: int | None = Field(default=None, description="Line number in the diff")
    body: str = Field(description="Comment body (markdown)")


class ReviewAction(BaseModel):
    """Action to take on a PR after audit."""

    event: str = Field(description="Review event: APPROVE, REQUEST_CHANGES, COMMENT")
    body: str = Field(description="Review summary body")
    comments: list[ReviewComment] = Field(default_factory=list, description="Inline review comments")
    labels: list[str] = Field(default_factory=list, description="Labels to apply")
