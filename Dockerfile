# OctoAuthor Tool Platform
# This container exposes MCP servers, discovery API, playbooks, and specs.
# It does NOT run the orchestrator — that connects remotely.

FROM python:3.11-slim AS base

# Security: non-root user
RUN groupadd -r octoauthor && useradd -r -g octoauthor -m octoauthor

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Install Playwright browsers
RUN uv run playwright install chromium

# Copy application code
COPY src/ src/
COPY specs/ specs/
COPY playbooks/ playbooks/
COPY VERSION ./

# Security: read-only filesystem for app code
# The /workspace volume is the only writable location
RUN mkdir -p /workspace && chown octoauthor:octoauthor /workspace

# Switch to non-root user
USER octoauthor

# Expose ports for MCP servers + discovery API
# 8000 = Discovery API + Playbook/Spec server
# 8100-8104 = MCP servers
EXPOSE 8000 8100 8101 8102 8103 8104

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD uv run python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Default command: start all services
CMD ["uv", "run", "octoauthor", "serve", "--all"]
