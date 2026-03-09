#!/bin/sh
# OctoAuthor container entrypoint
# Starts socat port forwards for target app ports, then runs the main service.
#
# OCTOAUTHOR_TARGET_HOST: IP of the host machine (e.g., WSL2 IP)
# OCTOAUTHOR_TARGET_PORTS: Comma-separated ports to forward (e.g., "3001,3000")
#
# This allows the headless browser inside Docker to reach target apps via
# localhost:<port>, keeping cookies and sessions working correctly.

set -e

# Ensure X11 socket directory exists (needed by Xvfb for VNC auth flow)
mkdir -p /tmp/.X11-unix

# SOCAT_TARGET_HOST is the IP to forward to (set in docker-compose environment)
TARGET_HOST="${SOCAT_TARGET_HOST:-${OCTOAUTHOR_TARGET_HOST:-}}"
TARGET_PORTS="${OCTOAUTHOR_TARGET_PORTS:-}"

if [ -n "$TARGET_HOST" ] && [ -n "$TARGET_PORTS" ]; then
    IFS=','
    for port in $TARGET_PORTS; do
        port=$(echo "$port" | tr -d ' ')
        if [ -n "$port" ]; then
            echo "Forwarding localhost:$port -> $TARGET_HOST:$port"
            socat TCP-LISTEN:${port},fork,reuseaddr TCP:${TARGET_HOST}:${port} &
        fi
    done
    unset IFS
fi

# Run the main command
exec "$@"
