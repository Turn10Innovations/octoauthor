# OctoAuthor Development Roadmap

**Version:** 0.1.0 (Pre-Alpha)
**Last Updated:** 2026-03-05

## Overview

OctoAuthor is a **Tool Platform** — it exposes MCP servers, specs, and playbooks that any orchestrator (OpenClaw, or any agentic framework) can connect to remotely. This roadmap covers the full implementation from core infrastructure through integrations.

### Current State

The project has solid foundations:
- Pydantic models for all domain objects (docs, capture, agents, providers, service)
- Settings via pydantic-settings with env var support
- CLI scaffold (version, serve, run, audit, validate commands — all stubbed)
- Specs (doc-standard.yaml, tag-schema.yaml)
- Playbooks (navigator, writer, graphic-designer, qa-reviewer)
- Threat model and security architecture docs
- GitHub Actions CI/CD workflows
- Docker deployment guide

What's missing: every MCP server, provider, security module, and service endpoint is an empty `__init__.py`.

### Dependency Graph

```
Phase 0 (Core Infrastructure)
|-- Phase 1 (Doc Store MCP Server)
|   |-- Phase 2 (Screenshot MCP Server)
|   |   \-- Phase 3 (Doc Writer MCP Server + MVP Demo)
|   |       |-- Phase 4 (Discovery API + Service Layer)
|   |       \-- Phase 5 (Security Module + Validate CLI)
|   |           \-- Phase 7 (Auditor Agent + CLI Audit)
|   \-- Phase 6 (App Inspector + Visual QA MCP Servers)
\-- Phase 8 (Integrations — after Phase 4)
```

---

## Phase 0: Core Infrastructure

**Goal:** Logging, provider abstraction, and test harness — the foundation everything else builds on.

### 0.1 Logging Module

**File:** `src/octoauthor/core/logging.py`

- `get_logger(name)` function returning a structured logger
- JSON-formatted log output for production, human-readable for dev
- Log level controlled by `OCTOAUTHOR_LOG_LEVEL` setting
- Context injection (correlation_id, agent_role) via `extra` dict
- No bare `print()` anywhere in the codebase

### 0.2 Provider Abstraction

**Directory:** `src/octoauthor/core/providers/`

```
providers/
  __init__.py       # get_provider() factory + registry
  base.py           # Abstract base: BaseProvider, ProviderResponse
  registry.py       # Provider registry (maps ProviderType -> class)
  ollama.py         # Ollama provider (OpenAI-compatible endpoint)
  anthropic.py      # Anthropic provider (optional dependency)
  openai_compat.py  # OpenAI-compatible provider (Groq, custom endpoints)
```

- `BaseProvider` ABC with `async generate(prompt, images?, system?)` method
- `ProviderResponse` model with `text`, `usage`, `model`, `provider` fields
- `get_provider(capability)` resolves from settings (text, vision, qa, audit)
- `ProviderRegistry` maps `ProviderType` enum to provider classes
- Lazy SDK imports — only import anthropic/openai/ollama when actually used
- All providers return the same `ProviderResponse` regardless of backend

### 0.3 Test Harness

**Files:**
- `tests/conftest.py` — shared fixtures (settings override, mock provider, tmp dirs)
- `tests/unit/test_models.py` — validation tests for all Pydantic models
- `tests/unit/test_settings.py` — settings loading, env var override, defaults
- `tests/unit/test_providers.py` — provider registry, mock generation

### Acceptance Criteria
- `uv run pytest` passes with model + settings + provider tests
- `get_logger(__name__)` works from any module
- `get_provider("text")` returns a working provider instance
- Provider abstraction tested with mock (no real API calls in unit tests)

---

## Phase 1: Doc Store MCP Server

**Goal:** First MCP server — establishes the pattern for all 5 servers.

### 1.1 MCP Server Structure

```
src/octoauthor/mcp_servers/doc_store/
  __init__.py
  server.py      # MCP server definition + tool registration
  tools.py       # Tool implementations (store, get, list, delete)
  models.py      # Input/output models for tools
  config.py      # Server-specific config (storage path, etc.)
  storage.py     # File-system storage backend
```

### 1.2 Tools

| Tool | Description |
|------|-------------|
| `store_doc` | Store a DocBundle (markdown + metadata) to the filesystem |
| `get_doc` | Retrieve a doc by tag |
| `list_docs` | List all stored docs with metadata |
| `delete_doc` | Remove a doc by tag |
| `store_screenshot` | Store a screenshot binary with metadata |
| `get_manifest` | Return the manifest.yaml index of all docs |

### 1.3 Manifest Management

- `manifest.yaml` in the doc output dir indexes all stored docs
- Updated atomically on every store/delete operation
- Contains tag, title, version, last_updated, screenshot_count per doc
- `get_manifest` tool returns the full manifest

### 1.4 MCP Server Registry + CLI Wiring

- `src/octoauthor/mcp_servers/registry.py` — maps server names to server instances
- CLI `serve` command looks up server by name, starts it on specified port
- Server runs over HTTP+SSE transport (not stdio)

### Acceptance Criteria
- `uv run octoauthor serve doc-store-server --port 8102` starts a working MCP server
- All 6 tools callable via MCP protocol
- Unit tests for all tools with temp directory fixtures
- Manifest stays consistent after store/delete sequences

---

## Phase 2: Screenshot MCP Server

**Goal:** Playwright-based browser automation for capturing screenshots.

### 2.1 Server Structure

```
src/octoauthor/mcp_servers/screenshot/
  __init__.py
  server.py       # MCP server + tool registration
  tools.py        # Tool implementations
  models.py       # Input/output models
  config.py       # Browser config (viewport, timeouts)
  browser.py      # Browser session management
  capture.py      # Screenshot capture + post-processing
```

### 2.2 Tools

| Tool | Description |
|------|-------------|
| `capture_screenshot` | Navigate to URL, capture full-page screenshot |
| `capture_flow` | Execute a sequence of interactions, capture at each step |
| `list_sessions` | List active browser sessions |
| `close_session` | Close a browser session |

### 2.3 Key Implementation Details

- Browser session pool (reuse sessions across captures)
- Viewport forced to 1280x800 (from settings)
- Light mode injection via CSS media query override
- Post-processing: EXIF strip (Pillow), size validation, PNG optimization
- Wait strategies: wait_for selector, networkidle, custom timeout
- Error recovery: retry on navigation timeout, clean error messages

### Acceptance Criteria
- `capture_screenshot` returns a valid PNG path
- Screenshots are exactly 1280x800, EXIF-stripped, under 500KB
- Integration test with a real browser (Playwright) against a test HTML page
- Browser sessions cleaned up on server shutdown

---

## Phase 3: Doc Writer MCP Server + MVP Demo

**Goal:** LLM-powered markdown generation. Combined with Phases 0-2, this completes the MVP: capture screenshots, generate docs, store them.

### 3.1 Server Structure

```
src/octoauthor/mcp_servers/doc_writer/
  __init__.py
  server.py       # MCP server + tool registration
  tools.py        # Tool implementations
  models.py       # Input/output models
  config.py       # Writer config (templates, prompt settings)
  prompts.py      # Prompt templates for doc generation
  templates/      # Jinja2 templates for guide structure
    guide.md.j2
    metadata.yaml.j2
```

### 3.2 Tools

| Tool | Description |
|------|-------------|
| `generate_guide` | Generate a complete DocBundle from CaptureResult |
| `generate_metadata` | Generate DocMetadata from route info |
| `rewrite_section` | Rewrite a specific section (for edits/corrections) |
| `validate_content` | Check content against doc-standard rules |

### 3.3 Key Implementation Details

- Uses provider abstraction (`get_provider("text")`) for all LLM calls
- Jinja2 templates define the guide structure (sections, formatting)
- Prompt engineering: system prompt loads doc-standard rules, few-shot examples
- Output parsing: extract structured steps from LLM response
- Content validation before returning (basic rule checks)

### 3.4 CLI `run` Command (MVP)

Wire up the end-to-end pipeline in the CLI:
1. Load config.yaml with CaptureConfig
2. Start screenshot server, capture all routes
3. For each CaptureResult, call doc-writer to generate DocBundle
4. Store each DocBundle via doc-store
5. Print summary with Rich

### MVP Milestone
- `uv run octoauthor run --config config.yaml --target http://localhost:3000`
- Captures screenshots of configured routes
- Generates markdown docs with metadata
- Stores docs and screenshots to the output directory
- Prints a summary of what was generated

### Acceptance Criteria
- `generate_guide` produces valid markdown matching doc-standard structure
- Generated metadata passes DocMetadata validation
- CLI `run` command works end-to-end (with a mock or real target app)
- Unit tests for prompt construction and output parsing

---

## Phase 4: Discovery API + Service Layer

**Goal:** HTTP service exposing discovery endpoint, playbooks, and specs.

### 4.1 Service Structure

```
src/octoauthor/service/
  __init__.py
  app.py          # Starlette/FastAPI app definition
  routes.py       # API route handlers
  middleware.py   # API key auth middleware
  startup.py      # Multi-server startup logic
```

### 4.2 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/discover` | GET | Discovery response (servers, playbooks, specs) |
| `/api/v1/playbooks/{name}` | GET | Serve a playbook YAML |
| `/api/v1/specs/{name}` | GET | Serve a spec YAML |

### 4.3 Key Implementation Details

- Starlette app (lightweight, async) — or FastAPI if we want OpenAPI docs
- API key authentication middleware (checks `X-API-Key` header)
- Separate API keys for orchestrator vs auditor access
- `/api/v1/discover` builds DiscoveryResponse from running server state
- Playbooks served from `playbooks/` directory
- Specs served from `specs/` directory
- `serve all` CLI command starts discovery API + all MCP servers

### Acceptance Criteria
- `curl http://localhost:8000/api/v1/discover` returns valid DiscoveryResponse JSON
- Playbooks and specs served correctly
- API key required for all endpoints (401 without key)
- `uv run octoauthor serve all` starts all servers

---

## Phase 5: Security Module + Validate CLI

**Goal:** Content security scanning and doc-standard compliance checking.

### 5.1 Module Structure

```
src/octoauthor/core/security/
  __init__.py
  sanitizer.py     # HTML/markdown sanitizer
  unicode.py       # Unicode homoglyph / invisible char scanner
  urls.py          # URL allowlist checker
  pii.py           # PII pattern scanner (emails, phones, SSNs)
  content.py       # Prohibited content checker (jargon, commands, etc.)
  validator.py     # Doc-standard compliance checker
  engine.py        # Validation engine composing all scanners
```

### 5.2 Scanners

| Scanner | What it checks |
|---------|----------------|
| `sanitizer` | Strips/flags dangerous HTML, script tags, event handlers |
| `unicode` | Detects invisible characters, homoglyphs, RTL overrides |
| `urls` | Checks URLs against domain allowlist |
| `pii` | Regex patterns for emails, phone numbers, SSNs, API keys |
| `content` | Prohibited content rules from doc-standard (jargon, commands) |
| `validator` | Full doc-standard compliance (structure, formatting, metadata) |

### 5.3 Validation Engine

- `ValidationEngine` composes all scanners
- Returns `ValidationResult` with pass/fail + list of `ValidationFinding`
- Each finding has severity, category, message, location
- Configurable: enable/disable individual scanners

### 5.4 CLI `validate` Command

```bash
uv run octoauthor validate ./docs/user-guide
```

- Scans all markdown files in the directory
- Runs all security scanners + doc-standard validator
- Rich output: table of findings, color-coded by severity
- Exit code 0 if all pass, 1 if any failures

### Acceptance Criteria
- Each scanner has dedicated unit tests
- Security test suite in `tests/security/`
- PII scanner catches common patterns (no false negatives on test data)
- `validate` CLI command produces useful output
- Doc-standard validator checks all rules from `specs/doc-standard.yaml`

---

## Phase 6: App Inspector + Visual QA MCP Servers

**Goal:** Complete the remaining two MCP servers.

### 6.1 App Inspector Server

```
src/octoauthor/mcp_servers/app_inspector/
  __init__.py
  server.py
  tools.py
  models.py
  inspector.py    # DOM analysis logic
```

**Tools:**
| Tool | Description |
|------|-------------|
| `inspect_page` | Analyze DOM structure, extract semantic elements |
| `discover_routes` | Find navigation links, build route map |
| `discover_forms` | Find forms, extract field labels/types |
| `discover_actions` | Find buttons, links, interactive elements |

### 6.2 Visual QA Server

```
src/octoauthor/mcp_servers/visual_qa/
  __init__.py
  server.py
  tools.py
  models.py
  comparator.py   # Visual diff logic
  ocr.py          # OCR for PII detection in screenshots
```

**Tools:**
| Tool | Description |
|------|-------------|
| `validate_screenshot` | Check screenshot meets spec (size, format, light mode) |
| `compare_screenshots` | Visual diff between two screenshots (detect UI changes) |
| `scan_pii_visual` | OCR scan for visible PII in screenshot |
| `check_annotations` | Validate annotation consistency |

### Acceptance Criteria
- All tools in both servers have unit tests
- App inspector works against test HTML pages
- Visual QA validates screenshot specs correctly
- PII OCR scanner catches visible emails/phone numbers in screenshots

---

## Phase 7: Auditor Agent + CLI Audit

**Goal:** PR review agent that combines security scanning with LLM-powered review.

### 7.1 Module Structure

```
src/octoauthor/auditor/
  __init__.py
  agent.py         # Audit orchestration logic
  github_client.py # GitHub API client (fetch PR, post review)
  reviewer.py      # LLM-powered content review
  reporter.py      # AuditReport generation
```

### 7.2 Audit Flow

1. Fetch PR diff from GitHub (changed/added files)
2. For each changed doc file:
   a. Run all security scanners (from Phase 5)
   b. Run doc-standard validator
   c. Run LLM review (content quality, accuracy, safety)
3. For each changed screenshot:
   a. Run visual QA (spec compliance, PII scan)
4. Aggregate findings into AuditReport
5. Post review to GitHub PR (approve, request changes, or comment)
6. Set labels (passed, flagged, blocked)

### 7.3 CLI `audit` Command

```bash
uv run octoauthor audit --pr 42 --repo turn10innovations/my-app
```

- Runs the full audit pipeline
- Prints AuditReport with Rich formatting
- Posts review to GitHub if `--post-review` flag set

### Acceptance Criteria
- Audit agent produces valid AuditReport
- GitHub client can fetch PR files and post reviews
- All security scanners integrated into audit pipeline
- LLM review uses provider abstraction (auditor capability)
- Unit tests with mock GitHub API and mock LLM responses

---

## Phase 8: Integrations

**Goal:** External system integrations for doc distribution.

### 8.1 GitHub Integration

```
src/octoauthor/integrations/github/
  __init__.py
  branch.py     # Branch creation/management
  pr.py         # PR creation, labeling
  client.py     # GitHub API client (shared with auditor)
```

### 8.2 Notion Integration

```
src/octoauthor/integrations/notion/
  __init__.py
  sync.py       # Sync DocBundles to Notion pages
  models.py     # Notion-specific models
```

### 8.3 React SDK

```
sdks/react/
  package.json
  src/
    HelpButton.tsx
    DocViewer.tsx
    OctoAuthorProvider.tsx
```

- `<HelpButton tag="company-maintenance" />` component
- Fetches doc from OctoAuthor API or static bundle
- Renders in a slide-out panel or modal

### 8.4 FastAPI SDK

```
sdks/fastapi/
  octoauthor_fastapi/
    __init__.py
    decorator.py   # @doc_tag() decorator
    middleware.py   # Help endpoint middleware
```

- `@doc_tag("company-maintenance")` decorator for routes
- Auto-registers `/help/{tag}` endpoint
- Serves docs from local directory or remote OctoAuthor instance

### Acceptance Criteria
- GitHub integration creates branches and PRs
- Notion sync creates/updates pages from DocBundles
- React SDK renders help button and fetches docs
- FastAPI SDK serves docs via decorator pattern

---

## Development Principles

1. **Each phase gets a feature branch** (`feature/phase-N-name`)
2. **Tests written alongside implementation** — no phase is "done" without tests
3. **Each phase has a PR** with clear description of what was added
4. **No phase skipping** — dependencies must be satisfied first
5. **Conventional commits** throughout (`feat:`, `fix:`, `test:`, `docs:`)
