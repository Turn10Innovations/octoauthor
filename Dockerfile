# OctoAuthor Tool Platform
# This container exposes MCP servers, discovery API, playbooks, and specs.
# It does NOT run the orchestrator — that connects remotely.

FROM python:3.11-slim AS base

# Security: non-root user
RUN groupadd -r octoauthor && useradd -r -g octoauthor -m octoauthor

# Install system dependencies for Playwright + git (for pipeline)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    socat \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    chromium \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock README.md ./

# Copy application code (needed for editable install)
COPY src/ src/
COPY specs/ specs/
COPY playbooks/ playbooks/
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY VERSION ./

# Install dependencies + the package itself (skip dev group, include anthropic)
RUN uv sync --frozen --no-group dev --extra providers-anthropic

# Install Playwright browsers + ALL system dependencies (headed mode needs X11 libs)
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN uv run playwright install --with-deps chromium

# Security: read-only filesystem for app code
# The /workspace volume is the only writable location
RUN mkdir -p /workspace && chown octoauthor:octoauthor /workspace

# Switch to non-root user
USER octoauthor

# Ensure runtime also uses the shared browser path
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# Expose single unified port (API + all MCP servers) + noVNC for auth
EXPOSE 9210 6080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD uv run python -c "import httpx; httpx.get('http://localhost:9210/health').raise_for_status()"

# Entrypoint sets up port forwards, then runs the command
ENTRYPOINT ["entrypoint.sh"]

# Default command: start all services (use 0.0.0.0 for container networking)
CMD ["uv", "run", "octoauthor", "serve", "all", "--host", "0.0.0.0"]
