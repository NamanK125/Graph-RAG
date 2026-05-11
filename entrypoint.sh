#!/bin/sh
set -e

# Ensure volume-mounted directories exist and are writable at runtime
mkdir -p /app/uploads /app/logs

exec "$@"
