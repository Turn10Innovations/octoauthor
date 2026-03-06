"""Service discovery models - structures for the OctoAuthor service API."""

from pydantic import BaseModel, Field, HttpUrl


class MCPServerInfo(BaseModel):
    """Information about an available MCP server."""

    name: str = Field(description="Server name (e.g., 'screenshot-server')")
    url: HttpUrl = Field(description="URL to connect to this MCP server")
    transport: str = Field(default="streamable-http", description="MCP transport type")
    description: str = Field(default="", description="What this server does")
    tools: list[str] = Field(default_factory=list, description="List of tool names this server provides")


class PlaybookInfo(BaseModel):
    """Information about an available agent playbook."""

    name: str = Field(description="Playbook name (e.g., 'writer')")
    display_name: str = Field(description="Human-readable name")
    url: HttpUrl = Field(description="URL to fetch the full playbook YAML")
    description: str = Field(default="", description="What this agent role does")
    requires_capabilities: list[str] = Field(
        default_factory=list,
        description="LLM capabilities needed (e.g., ['text'], ['vision'])",
    )


class SpecInfo(BaseModel):
    """Information about an available spec file."""

    name: str = Field(description="Spec name (e.g., 'doc-standard')")
    url: HttpUrl = Field(description="URL to fetch the full spec")
    version: str = Field(description="Spec version")


class DiscoveryResponse(BaseModel):
    """Response from the /api/v1/discover endpoint.

    This is the entry point for any orchestrator connecting to OctoAuthor.
    It tells the orchestrator: what tools are available, what roles exist,
    and what standards to follow.
    """

    service: str = Field(default="octoauthor", description="Service identifier")
    version: str = Field(description="OctoAuthor version")
    mcp_servers: list[MCPServerInfo] = Field(description="Available MCP servers to connect to")
    playbooks: list[PlaybookInfo] = Field(description="Available agent playbooks")
    specs: dict[str, str] = Field(description="Available spec files (name → URL)")
    health: str = Field(default="ok", description="Service health status")
