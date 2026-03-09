"""URL rewriting for containerized environments.

When OctoAuthor runs in Docker, it can't reach 'localhost' on the host machine.
This module rewrites localhost URLs to a Docker-accessible host (e.g.,
'host.docker.internal') based on the OCTOAUTHOR_TARGET_HOST setting.
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse, urlunparse

from octoauthor.core.config import get_settings
from octoauthor.core.logging import get_logger

_LOCALHOST_NAMES = {"localhost", "127.0.0.1", "0.0.0.0"}  # noqa: S104

logger = get_logger(__name__)

# Cache the resolved IPv4 address for the target host
_resolved_host_cache: dict[str, str] = {}


def _resolve_to_ipv4(hostname: str) -> str:
    """Resolve a hostname to an IPv4 address, with caching.

    On WSL2, host.docker.internal may resolve to IPv6 only which is often
    unreachable from containers. Force IPv4 resolution.
    """
    if hostname in _resolved_host_cache:
        return _resolved_host_cache[hostname]

    try:
        # AF_INET forces IPv4 resolution
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if results:
            ipv4 = results[0][4][0]
            _resolved_host_cache[hostname] = ipv4
            logger.info("Resolved %s to IPv4: %s", hostname, ipv4)
            return ipv4
    except socket.gaierror:
        logger.warning("Could not resolve %s to IPv4, using as-is", hostname)

    _resolved_host_cache[hostname] = hostname
    return hostname


def rewrite_url(url: str) -> str:
    """Rewrite localhost URLs to the configured target host.

    If OCTOAUTHOR_TARGET_HOST is not set, the URL is returned unchanged.
    Only rewrites when the hostname is localhost/127.0.0.1/0.0.0.0.
    Resolves the target host to IPv4 to avoid WSL2 IPv6 issues.
    """
    target_host = get_settings().target_host
    if not target_host:
        return url

    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname and hostname in _LOCALHOST_NAMES:
        # Resolve to IPv4 to avoid WSL2/Docker IPv6 connectivity issues
        resolved = _resolve_to_ipv4(target_host)
        port = parsed.port
        new_netloc = f"{resolved}:{port}" if port else resolved
        return urlunparse(parsed._replace(netloc=new_netloc))

    return url
