#!/usr/bin/env bash
set -euo pipefail

# Resolve project root (directory containing this script)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "[start_belong] Error: uv is required but not found in PATH." >&2
  exit 1
fi

# Ensure dependencies and virtualenv are in place
uv sync

# Activate the project virtualenv
source "$PROJECT_ROOT/.venv/bin/activate"

# Rebuild Tailwind output once before watching
npx tailwindcss@3.4.13 -i assets/tailwind.css -o static/css/tailwind.css --minify

# Start Tailwind watcher in the background
npx tailwindcss@3.4.13 -i assets/tailwind.css -o static/css/tailwind.css --watch --minify &
TAILWIND_PID=$!

echo "[start_belong] Tailwind watcher running (PID: $TAILWIND_PID)"

die() {
  local exit_code=$?
  if ps -p "$TAILWIND_PID" >/dev/null 2>&1; then
    kill "$TAILWIND_PID" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}

trap die EXIT

# Run Django development server on port 8000
python manage.py runserver 0.0.0.0:8000
