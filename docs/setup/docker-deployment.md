# OctoAuthor Docker Deployment Guide

## Tool Platform Model

OctoAuthor runs in Docker as a locked-down Tool Platform. External orchestrators like OpenClaw connect to it remotely. If anything blows up, it's just a container — `docker compose down && docker compose up` and you're back.

## Architecture

```
Your Dev Machine
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Docker: OctoAuthor (Tool Platform)                  │
│  ┌───────────────────────────────────────────────┐  │
│  │ Discovery API        :8000                    │  │
│  │ screenshot-server    :8100                    │  │
│  │ doc-writer-server    :8101                    │  │
│  │ doc-store-server     :8102                    │  │
│  │ visual-qa-server     :8103                    │  │
│  │ app-inspector        :8104                    │  │
│  │                                               │  │
│  │ Volume: /workspace (only writable location)   │  │
│  │ Filesystem: read-only                         │  │
│  │ User: non-root                                │  │
│  │ Capabilities: ALL dropped                     │  │
│  └──────────┬────────────────────────────────────┘  │
│             │                                       │
│  Host services OctoAuthor can reach:                │
│  ┌──────────┴────────────────────────────────────┐  │
│  │ Ollama         host.docker.internal:11434     │  │
│  │ Target App     host.docker.internal:3000      │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
         ▲
         │ HTTP+SSE (MCP protocol)
         │
┌────────┴──────────────────┐
│ OpenClaw (separate server) │
│ Connects to :8000-8104     │
│ Uses tools, reads specs    │
│ Creates PRs via GitHub     │
└───────────────────────────┘
```

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/turn10innovations/octoauthor.git
cd octoauthor
cp .env.example .env
# Edit .env with your API keys and settings

# 2. Build and run
docker compose up -d

# 3. Verify it's running
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/discover

# 4. Point OpenClaw at the discovery endpoint
# In your OpenClaw config:
#   mcp_servers:
#     - url: http://your-dev-machine:8000/api/v1/discover
```

## Environment Variables

Create a `.env` file (never commit this):

```bash
# API authentication
OCTOAUTHOR_API_KEY=your-secret-key-for-orchestrator-access
OCTOAUTHOR_AUDITOR_API_KEY=separate-key-for-auditor-access

# Logging
OCTOAUTHOR_LOG_LEVEL=INFO

# Port overrides (defaults shown)
OCTOAUTHOR_API_PORT=8000
OCTOAUTHOR_MCP_SCREENSHOT=8100
OCTOAUTHOR_MCP_WRITER=8101
OCTOAUTHOR_MCP_STORE=8102
OCTOAUTHOR_MCP_VISUAL=8103
OCTOAUTHOR_MCP_INSPECTOR=8104
```

## Connecting to Host Services

OctoAuthor in Docker needs to reach services on your dev machine:

### Ollama (local LLM)

Ollama runs on the host machine. OctoAuthor reaches it via `host.docker.internal`:

```bash
# In your OctoAuthor config or .env:
OCTOAUTHOR_TEXT_BASE_URL=http://host.docker.internal:11434

# Make sure Ollama is listening on all interfaces:
OLLAMA_HOST=0.0.0.0 ollama serve
```

### Target Application (for screenshots)

Your running web app that OctoAuthor will document:

```bash
# In your capture config:
base_url: http://host.docker.internal:3000
```

### External APIs (Anthropic, OpenAI)

For the auditor or QA agents that use cloud models:

```bash
# These are passed through as env vars in docker-compose.yaml
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Security Hardening

### What the container CAN do:
- Serve MCP tools over HTTP+SSE on exposed ports
- Read playbooks and specs (baked into image)
- Write to `/workspace` volume (doc output)
- Connect to Ollama on host (for local model inference)
- Connect to target app on host (for Playwright screenshots)

### What the container CANNOT do:
- Access the host filesystem (except `/workspace` volume)
- Run shell commands (no shell tools in MCP servers)
- Escalate privileges (`no-new-privileges`, all caps dropped)
- Modify its own code (`read-only` filesystem)
- Access arbitrary network endpoints (unless explicitly configured)
- Survive a `docker compose down` (ephemeral by design)

### If something goes wrong:

```bash
# Nuclear option — blow it away and start fresh
docker compose down -v  # -v removes the workspace volume too
docker compose up -d

# Less nuclear — restart without losing workspace
docker compose restart

# Check what happened
docker compose logs octoauthor --tail 100
```

## Connecting OpenClaw

On the OpenClaw server, configure it to connect to OctoAuthor:

```yaml
# OpenClaw MCP configuration
mcp_servers:
  octoauthor-discovery:
    url: http://your-dev-machine:8000/api/v1/discover
    api_key: ${OCTOAUTHOR_API_KEY}

# Or connect to individual MCP servers directly:
mcp_servers:
  octoauthor-screenshot:
    url: http://your-dev-machine:8100/mcp
    transport: sse
    api_key: ${OCTOAUTHOR_API_KEY}
  octoauthor-doc-store:
    url: http://your-dev-machine:8102/mcp
    transport: sse
    api_key: ${OCTOAUTHOR_API_KEY}
```

## GitHub Integration

OctoAuthor itself doesn't push to GitHub — the orchestrator does. But the auditor needs read access to PRs:

```bash
# Orchestrator (OpenClaw) GitHub token — can create branches and PRs
# Configured on the OpenClaw server, NOT in OctoAuthor
GITHUB_TOKEN=ghp_orchestrator_token

# Auditor GitHub token — read-only on PRs, can post review comments
# Configured on the auditor server or in OctoAuthor .env
OCTOAUTHOR_AUDITOR_GITHUB_TOKEN=ghp_auditor_readonly_token
```
