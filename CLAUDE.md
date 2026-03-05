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

### 5. Agent Pattern (OpenClaw Skills)

Agents are packaged as OpenClaw skills (markdown-defined). Each agent has a clear role, required capabilities, and output contract.

```yaml
# skills/{agent_name}.md - OpenClaw skill definition
name: octoauthor-writer
description: Generates step-by-step user documentation from structured capture data
requires:
  capabilities: [text]
  mcp_servers: [doc-store, doc-writer]
input: CaptureData (structured screenshots + DOM analysis)
output: DocBundle (markdown files + metadata)
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

```
OctoAuthor Architecture:

OpenClaw (orchestrator - UNTRUSTED worker)
├── MCP Servers (tools)
│   ├── screenshot-server    → Playwright navigation + capture
│   ├── doc-writer-server    → MD generation from structured data
│   ├── visual-qa-server     → Screenshot validation + visual diff
│   ├── doc-store-server     → Read/write/query doc repository
│   └── app-inspector-server → DOM analysis, route discovery
│
├── Agents (OpenClaw skills)
│   ├── Navigator            → Walks app, captures flows
│   ├── Writer               → Generates prose from captures
│   ├── Graphic Designer     → Validates/annotates screenshots
│   ├── QA Reviewer          → Checks docs against style guide
│   └── Orchestrator         → Coordinates the pipeline
│
├── Auditor (SEPARATE trusted process)
│   ├── Content safety scan
│   ├── Prompt injection detection
│   ├── PII/data leakage OCR
│   └── Posts review on PR
│
└── Security Gates
    ├── Gate 1: GitHub Actions (static analysis, linting, secret scanning)
    ├── Gate 2: Auditor Agent (AI security review)
    └── Gate 3: Human Review (HITL merge approval)
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
| Agent Skills | `skills/` |
| Core Config | `src/octoauthor/core/config/` |
| Provider Abstraction | `src/octoauthor/core/providers/` |
| Security / Auditor | `src/octoauthor/agents/auditor/` |
| Pydantic Models | `src/octoauthor/core/models/` |
| Doc Standard Spec | `specs/doc-standard.yaml` |
| Threat Model | `docs/architecture/threat-model.md` |
| GitHub Actions | `.github/workflows/` |
| Integration SDKs | `sdks/` |

## Git Workflow

- Main branch: `master` (protected, requires PR + review)
- Development branch: `dev`
- Feature branches: `feature/{name}`
- OpenClaw branches: `openclaw/doc-update-{date}-{hash}` (auto-created, limited access)
- Use conventional commit messages
