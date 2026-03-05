"""Notion-specific models for doc sync."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NotionPageRef(BaseModel):
    """Reference to a Notion page."""

    page_id: str = Field(description="Notion page ID")
    url: str = Field(default="", description="Notion page URL")
    title: str = Field(default="", description="Page title")


class NotionSyncResult(BaseModel):
    """Result from syncing a doc to Notion."""

    tag: str = Field(description="Doc tag that was synced")
    page_id: str = Field(description="Notion page ID")
    url: str = Field(description="Notion page URL")
    created: bool = Field(description="True if page was created, False if updated")


class NotionSyncConfig(BaseModel):
    """Configuration for Notion sync."""

    database_id: str = Field(description="Notion database ID to sync to")
    token: str = Field(description="Notion integration token")
    tag_property: str = Field(default="Tag", description="Database property name for doc tag")
    title_property: str = Field(default="Name", description="Database property name for title")
    category_property: str = Field(default="Category", description="Database property name for category")
    version_property: str = Field(default="Version", description="Database property name for version")
