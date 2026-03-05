"""API route handlers for the OctoAuthor service."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from starlette.requests import Request

from octoauthor import __version__
from octoauthor.core.logging import get_logger
from octoauthor.core.models.service import DiscoveryResponse, MCPServerInfo, PlaybookInfo
from octoauthor.mcp_servers.registry import get_server_ports

logger = get_logger(__name__)


def _get_host(request: Request) -> str:
    """Get the base URL from the request."""
    return f"{request.url.scheme}://{request.url.netloc}"


async def health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "version": __version__})


async def discover(request: Request) -> JSONResponse:
    """Discovery endpoint — tells orchestrators what's available."""
    host = _get_host(request)

    mcp_servers = []
    for name, port in get_server_ports().items():
        mcp_servers.append(
            MCPServerInfo(
                name=name,
                url=f"{host.rsplit(':', 1)[0]}:{port}/mcp",
                description=_server_descriptions.get(name, ""),
                tools=[],
            ).model_dump(mode="json")
        )

    playbooks = []
    playbooks_dir = Path("playbooks")
    if playbooks_dir.exists():
        for pb_file in sorted(playbooks_dir.glob("*.yaml")):
            raw = yaml.safe_load(pb_file.read_text()) or {}
            playbooks.append(
                PlaybookInfo(
                    name=raw.get("name", pb_file.stem),
                    display_name=raw.get("display_name", pb_file.stem.replace("-", " ").title()),
                    url=f"{host}/api/v1/playbooks/{pb_file.stem}",
                    description=raw.get("description", ""),
                    requires_capabilities=raw.get("requires", {}).get("capabilities", []),
                ).model_dump(mode="json")
            )

    specs: dict[str, str] = {}
    specs_dir = Path("specs")
    if specs_dir.exists():
        for spec_file in sorted(specs_dir.glob("*.yaml")):
            specs[spec_file.stem] = f"{host}/api/v1/specs/{spec_file.stem}"

    response = DiscoveryResponse(
        version=__version__,
        mcp_servers=[MCPServerInfo(**s) for s in mcp_servers],
        playbooks=[PlaybookInfo(**p) for p in playbooks],
        specs=specs,
    )
    return JSONResponse(response.model_dump(mode="json"))


async def get_playbook(request: Request) -> Response:
    """Serve a playbook YAML file."""
    name = request.path_params["name"]
    path = Path("playbooks") / f"{name}.yaml"
    if not path.exists():
        return JSONResponse({"error": f"Playbook not found: {name}"}, status_code=404)
    return Response(path.read_text(), media_type="text/yaml")


async def get_spec(request: Request) -> Response:
    """Serve a spec YAML file."""
    name = request.path_params["name"]
    path = Path("specs") / f"{name}.yaml"
    if not path.exists():
        return JSONResponse({"error": f"Spec not found: {name}"}, status_code=404)
    return Response(path.read_text(), media_type="text/yaml")


_server_descriptions: dict[str, str] = {
    "doc-store-server": "Document storage and manifest management",
    "screenshot-server": "Browser automation and screenshot capture",
    "doc-writer-server": "LLM-powered documentation generation",
    "visual-qa-server": "Screenshot validation and visual diff",
    "app-inspector-server": "DOM analysis and route discovery",
}
