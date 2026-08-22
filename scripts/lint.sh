#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MAX_LINES=350
FAILED=0

uv run ruff check demo_agent
uv run ruff format --check demo_agent

while IFS= read -r file; do
  lines="$(wc -l < "$file")"
  if [ "$lines" -gt "$MAX_LINES" ]; then
    echo "ERROR: $file has $lines lines (limit $MAX_LINES)" >&2
    FAILED=1
  fi
done < <(find demo_agent -name '*.py' -type f)

if [ "$FAILED" -ne 0 ]; then
  exit 1
fi

echo "lint OK"
