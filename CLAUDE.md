# OctoAuthor - Claude Code Project Memory

AI-powered user documentation generator with zero-trust security architecture.
Mascot: Arthur the Octopus. Domain: octoauthor.com

## Use Coding Brain for Project Knowledge

**ALWAYS check coding-brain MCP server first** for project-specific knowledge before guessing or trying random approaches.

```bash
mcp__coding-brain__coding_brain_recall(query="octoauthor architecture")
```

## Ask Questions First

**NEVER assume when instructions are unclear.** Ask clarifying questions, confirm understanding, and propose approach before non-trivial changes.

## Critical Rules (Zero Tolerance)

### 0. Use `uv` for ALL Package Management

**NEVER use `pip`, `pip install`, `pip freeze`, or `python -m pip`.** Always use `uv`.

```bash
# CORRECT
uv add httpx                      # Add a dependency
uv add --dev pytest-mock          # Add a dev dependency
uv add --optional providers-anthropic anthropic  # Add to optional group
uv sync                           # Install/sync all dependencies
uv sync --extra providers-ollama  # Install with optional group
uv run pytest                     # Run commands in the venv
uv run python -c "..."            # Run Python in the venv
uv run mypy src/                  # Run tools in the venv
uv lock                           # Update lock file

# WRONG - never use these
pip install httpx
pip freeze > requirements.txt
python -m pytest
```

- `pyproject.toml` is the single source of truth for dependencies
- `uv.lock` is committed to the repo (deterministic builds)
- All CLI commands (`pytest`, `mypy`, `ruff`, `octoauthor`) run via `uv run`
- No `requirements.txt` — everything is in `pyproject.toml`

### 1. Pydantic Everywhere

All data structures, configs, API inputs/outputs, and inter-agent messages MUST use Pydantic models. No raw dicts for structured data.

```python
# CORRECT
class DocMetadata(BaseModel):
    tag: str
    title: str
    version: str
    last_updated: date
    applies_to: list[str]

# WRONG - never pass raw dicts between components
metadata = {"tag": "company-maintenance", "title": "..."}
```

### 2. Model-Agnostic Provider Pattern

NEVER import provider SDKs directly in business logic. Always go through the provider abstraction layer.

```python
# CORRECT
from octoauthor.core.providers import get_provider
provider = get_provider("text")  # Resolves from config
response = await provider.generate(prompt="...")

# WRONG - leaks provider dependency into business logic
from anthropic import Anthropic
client = Anthropic()
```

### 3. Zero-Trust Security Model

OpenClaw is an UNTRUSTED worker. The Auditor agent runs as a SEPARATE process with its own credentials. Never combine them.

| Component | Trust Level | Access |
|-----------|------------|--------|
| OpenClaw | UNTRUSTED | Feature branches only, PR creation only |
| Auditor Agent | TRUSTED | Read-only on PRs, post reviews |
| GitHub Actions | TRUSTED | Static analysis, gating |
| Human Reviewer | AUTHORITY | Merge approval |

### 4. MCP Server Pattern

Each MCP server is a single-responsibility tool provider. Servers expose tools via the MCP protocol and MUST NOT contain business logic beyond their specific domain.

```python
# Each MCP server follows this structure:
src/octoauthor/mcp_servers/{server_name}/
├── __init__.py
├── server.py          # MCP server definition + tool registration
├── tools.py           # Tool implementations
├── models.py          # Pydantic models for inputs/outputs
└── config.py          # Server-specific configuration
```

### 5. OctoAuthor is a Tool Platform, Not an Orchestrator

OctoAuthor is a **Tool Platform** that exposes MCP servers, specs, and playbooks. The orchestrator (OpenClaw, or any agentic framework) is a **separate system** that connects remotely, discovers capabilities, and does the work.

**OctoAuthor NEVER embeds or runs the orchestrator.** It provides:
- MCP servers over **HTTP+SSE** (remotely connectable, not stdio)
- A **discovery endpoint** (`GET /api/v1/discover`) listing available tools, specs, and playbooks
- **Agent playbooks** (portable YAML role definitions, not tied to any orchestrator)
- **Spec files** the orchestrator reads to understand quality standards

```
┌─────────────────────────────────────────────┐
│  OpenClaw / Any Orchestrator                │
│  - Runs on its own server/machine           │
│  - Connects to OctoAuthor remotely          │
│  - Reads playbooks to understand its role   │
│  - Uses MCP tools to do the work            │
└──────────────┬──────────────────────────────┘
               │ HTTP+SSE (MCP protocol)
               ▼
┌─────────────────────────────────────────────┐
│  OctoAuthor Tool Platform                   │
│  - Exposes MCP servers as HTTP endpoints    │
│  - Serves playbooks and specs               │
│  - Provides discovery API                   │
│  - Does NOT know or care who connects       │
└─────────────────────────────────────────────┘
```

#### Agent Playbooks (orchestrator-agnostic)

```yaml
# playbooks/writer.yaml - any orchestrator can consume this
name: writer
description: Generates step-by-step user documentation from structured capture data
role: |
  You are a technical writer specializing in user-facing documentation.
  You write clear, imperative step-by-step guides with screenshots.
  You follow the documentation standard strictly.
requires:
  capabilities: [text]
  mcp_servers: [doc-store, doc-writer]
  specs: [doc-standard.yaml]
input:
  type: CaptureResult
  description: Structured screenshots + DOM analysis from the navigator
output:
  type: DocBundle
  description: Complete markdown guide with metadata and screenshot references
constraints:
  - Must pass all rules in doc-standard.yaml
  - Max 10 steps per guide
  - Imperative voice only
```

#### Discovery Endpoint

```json
GET /api/v1/discover
{
  "service": "octoauthor",
  "version": "0.1.0",
  "mcp_servers": [
    {"name": "screenshot-server", "url": "http://host:8100/mcp", "transport": "sse"},
    {"name": "doc-writer-server", "url": "http://host:8101/mcp", "transport": "sse"},
    {"name": "doc-store-server", "url": "http://host:8102/mcp", "transport": "sse"},
    {"name": "visual-qa-server", "url": "http://host:8103/mcp", "transport": "sse"},
    {"name": "app-inspector-server", "url": "http://host:8104/mcp", "transport": "sse"}
  ],
  "playbooks": [
    {"name": "navigator", "url": "http://host:8000/api/v1/playbooks/navigator"},
    {"name": "writer", "url": "http://host:8000/api/v1/playbooks/writer"},
    {"name": "graphic-designer", "url": "http://host:8000/api/v1/playbooks/graphic-designer"},
    {"name": "qa-reviewer", "url": "http://host:8000/api/v1/playbooks/qa-reviewer"}
  ],
  "specs": {
    "doc_standard": "http://host:8000/api/v1/specs/doc-standard",
    "tag_schema": "http://host:8000/api/v1/specs/tag-schema"
  }
}
```

### 6. No Hardcoding

Never hardcode URLs, file paths, model names, credentials, or configuration values. Everything comes from config files or environment variables.

```python
# CORRECT
from octoauthor.core.config import get_settings
settings = get_settings()
output_dir = settings.doc_output_dir

# WRONG
output_dir = "/home/user/docs/output"
```

### 7. Error Handling & Logging

```python
from octoauthor.core.logging import get_logger
logger = get_logger(__name__)

# ALWAYS log with context, NEVER bare except or print()
try:
    result = await capture_screenshot(url)
except PlaywrightError as e:
    logger.error("Screenshot capture failed", exc_info=True, extra={
        "url": url,
        "step": step_number,
    })
    raise CaptureError(f"Failed to capture {url}") from e
```

### 8. File Size Limits

- Max 2,000 lines per Python file. Split into modules if approaching limit.
- Max 500 lines per test file.
- Max 100 lines per Pydantic model file (split into domain-specific model files).

### 9. Testing Requirements

- All MCP server tools MUST have unit tests
- All Pydantic models MUST have validation tests
- Security checks MUST have dedicated test suite in `tests/security/`
- Use pytest fixtures, no test data hardcoding

### 10. Documentation Standards Enforcement

OctoAuthor generates docs that MUST pass its own standards. The specs in `specs/` are machine-readable and enforced by the QA agent. See `specs/doc-standard.yaml` for the full ruleset.

## Project Architecture

OctoAuthor follows the **Tool Platform** pattern: OctoAuthor is the platform (service + tools), the orchestrator connects remotely and does the work.

```
ORCHESTRATOR (external, untrusted)         TOOL PLATFORM (OctoAuthor service)
┌──────────────────────────┐               ┌──────────────────────────────────┐
│  OpenClaw / Any Agent    │               │  OctoAuthor Service              │
│  Framework               │   HTTP+SSE    │                                  │
│                          │◄─────────────►│  Discovery API (/api/v1/discover)│
│  Reads playbooks         │   (MCP)       │                                  │
│  Uses MCP tools          │               │  MCP Servers (the tools):        │
│  Follows specs           │               │  ├── screenshot-server  :8100    │
│  Creates PRs             │               │  ├── doc-writer-server  :8101    │
│                          │               │  ├── doc-store-server   :8102    │
│  NOT part of this repo.  │               │  ├── visual-qa-server   :8103    │
│  Runs on its own server. │               │  └── app-inspector      :8104    │
└──────────────────────────┘               │                                  │
                                           │  Playbooks (agent role defs):    │
AUDITOR (separate, trusted)                │  ├── navigator.yaml              │
┌──────────────────────────┐               │  ├── writer.yaml                 │
│  Auditor Agent           │   HTTP+SSE    │  ├── graphic-designer.yaml       │
│  (own credentials,       │◄─────────────►│  └── qa-reviewer.yaml            │
│   own server)            │   (MCP)       │                                  │
│                          │               │  Specs (quality standards):       │
│  Reviews PRs             │               │  ├── doc-standard.yaml           │
│  Posts findings          │               │  └── tag-schema.yaml             │
│  Labels pass/flag/block  │               └──────────────────────────────────┘
└──────────────────────────┘
                                           SECURITY GATES (GitHub, independent)
                                           ┌──────────────────────────────────┐
                                           │  Gate 1: GitHub Actions (static) │
                                           │  Gate 2: Auditor Agent (AI)      │
                                           │  Gate 3: Human Review (HITL)     │
                                           └──────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Package Manager | uv |
| Data Models | Pydantic v2 |
| Config | pydantic-settings |
| Browser Automation | Playwright |
| MCP Framework | mcp (official SDK) |
| CLI | Typer + Rich |
| HTTP Client | httpx |
| Templates | Jinja2 |
| Image Processing | Pillow |
| Linting | Ruff |
| Type Checking | mypy (strict) |
| Testing | pytest + pytest-asyncio |

## Common Commands

```bash
# Install dependencies
uv sync

# Install with specific provider
uv sync --extra providers-anthropic
uv sync --extra providers-ollama

# Run tests
PYTHONPATH=src uv run pytest

# Type check
uv run mypy src/

# Lint
uv run ruff check src/
uv run ruff format src/

# Run a specific MCP server (for development)
uv run octoauthor serve screenshot-server

# Run the full pipeline
uv run octoauthor run --config config.yaml --target ./my-app
```

## Key File Locations

| What | Where |
|------|-------|
| MCP Servers | `src/octoauthor/mcp_servers/` |
| Service Layer (discovery, API) | `src/octoauthor/service/` |
| Playbooks (agent role defs) | `playbooks/` |
| Core Config | `src/octoauthor/core/config/` |
| Provider Abstraction | `src/octoauthor/core/providers/` |
| Auditor | `src/octoauthor/auditor/` |
| Pydantic Models | `src/octoauthor/core/models/` |
| Doc Standard Spec | `specs/doc-standard.yaml` |
| Tag Schema | `specs/tag-schema.yaml` |
| Threat Model | `docs/architecture/threat-model.md` |
| GitHub Actions | `.github/workflows/` |
| Integration SDKs | `sdks/` |

## Git Workflow

- Main branch: `master` (protected, requires PR + review)
- Development branch: `dev`
- Feature branches: `feature/{name}`
- OpenClaw branches: `octoauthor/doc-update-{date}-{hash}` (auto-created, limited access)
- Use conventional commit messages
