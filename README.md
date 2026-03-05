# OctoAuthor

**AI-powered user documentation generator with zero-trust security.**

Meet Arthur the Octopus — your autonomous documentation assistant that generates, validates, and maintains step-by-step user guides with screenshots, all behind a multi-layer security review pipeline.

## What OctoAuthor Does

OctoAuthor navigates your running web application, captures screenshots, and generates user-facing documentation — complete with step-by-step guides, annotated screenshots, and contextual help that maps to specific screens in your app.

Unlike commercial tools (Scribe, Tango, Guidde), OctoAuthor is:
- **Open source** and self-hosted
- **Model-agnostic** — use Ollama, OpenAI, Anthropic, Groq, or any provider
- **Security-first** — zero-trust architecture with multi-layer review
- **Developer-friendly** — ships as composable MCP servers and CLI tools
- **CI/CD integrated** — docs update via PR workflow with human approval

## Architecture

Think of OctoAuthor as a garage stocked with specialized tools — any mechanic (orchestrator) can walk in, discover what's available, and get to work. OctoAuthor doesn't care who the mechanic is; it just provides the tools, the specs, and the quality standards.

```
Orchestrator (external, untrusted)        OctoAuthor Tool Platform
┌────────────────────────────┐            ┌─────────────────────────────────┐
│ OpenClaw / Any Agent       │  HTTP+SSE  │ MCP Servers (the tools):        │
│ Framework                  │◄──────────►│ ├── screenshot-server  :8100    │
│                            │   (MCP)    │ ├── doc-writer-server  :8101    │
│ Reads playbooks            │            │ ├── doc-store-server   :8102    │
│ Uses MCP tools             │            │ ├── visual-qa-server   :8103    │
│ Follows specs              │            │ └── app-inspector      :8104    │
│ Creates PRs                │            │                                 │
└────────────────────────────┘            │ Discovery API (/api/v1/discover)│
                                          │ Playbooks (agent role defs)     │
Auditor (separate, trusted)               │ Specs (quality standards)       │
┌────────────────────────────┐            └─────────────────────────────────┘
│ Security review agent      │  HTTP+SSE
│ (own credentials, own box) │◄──────────►  (same MCP servers)
│ Reviews PRs, posts labels  │
└────────────────────────────┘

Security Gates (GitHub, independent)
├── Gate 1: GitHub Actions (static analysis)
├── Gate 2: Auditor Agent (AI security review)
└── Gate 3: Human Review (merge approval)
```

## Zero-Trust Security Model

OctoAuthor treats the autonomous worker as **untrusted**. Everything it generates passes through multiple independent review layers before reaching any protected branch.

| Component | Trust Level | Access |
|-----------|------------|--------|
| OpenClaw (worker) | Untrusted | Feature branches only |
| Auditor Agent | Trusted | Separate process, read-only |
| GitHub Actions | Trusted | Static analysis |
| Human Reviewer | Authority | Final merge approval |

See [Threat Model](docs/architecture/threat-model.md) for the full security architecture.

## Quick Start

```bash
# Install
pip install uv
uv sync

# With a specific AI provider
uv sync --extra providers-anthropic
uv sync --extra providers-ollama

# Validate existing docs
uv run octoauthor validate ./docs/user-guide

# Run the full pipeline (requires running target app)
uv run octoauthor run --config config.yaml --target http://localhost:3000
```

## In-App Contextual Help

OctoAuthor generates docs tagged to specific screens. Integrate the help button into your app:

**React:**
```tsx
import { HelpButton } from '@octoauthor/react'

<h1>Companies <HelpButton tag="company-maintenance" /></h1>
```

**FastAPI:**
```python
from octoauthor.sdks.fastapi import get_doc

@router.get("/help/{tag}")
async def get_help(tag: str):
    return get_doc(tag, docs_dir="docs/user-guide")
```

## Configuration

```yaml
# config.yaml
app_name: MyApp
base_url: http://localhost:3000
viewport_width: 1280
viewport_height: 800
light_mode_only: true

providers:
  text:
    provider: ollama
    model: qwen3:32b
  vision:
    provider: anthropic
    model: claude-sonnet-4-6
  audit:
    provider: anthropic
    model: claude-sonnet-4-6

routes:
  - route: /companies
    tag: company-maintenance
    title: Company Management
  - route: /users
    tag: user-management
    title: User Management
```

## Documentation Standard

All generated docs follow a strict, machine-readable spec. See [specs/doc-standard.yaml](specs/doc-standard.yaml).

Key rules:
- Imperative voice ("Click Save", not "You should click Save")
- Max 10 steps per guide
- All screenshots: 1280x800, light mode, demo data only
- No terminal commands, code snippets, or technical jargon
- Consistent terminology enforced by glossary

## Contributing

We welcome contributions! OctoAuthor is designed with clear contribution surfaces:

- **MCP Servers** — add new tool capabilities
- **Agent Skills** — new agent behaviors for OpenClaw
- **Provider Integrations** — support new LLM providers
- **SDK Integrations** — React, Vue, Angular, FastAPI, Express, etc.
- **Doc Standard** — propose spec improvements

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT

---

*Built by [Turn10 Innovations](https://turn10innovations.com) — powering responsible autonomous AI.*
