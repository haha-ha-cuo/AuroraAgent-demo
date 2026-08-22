#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_VERSION="${PYTHON_VERSION:-3.13}"
SIDECAR_DIR="$ROOT/apps/desktop/src-tauri/resources/sidecar"
TMP_VENV="$ROOT/.tmp-sidecar-venv"

rm -rf "$SIDECAR_DIR" "$TMP_VENV"
mkdir -p "$SIDECAR_DIR"

uv python install "$PYTHON_VERSION"

PYTHON_BIN="$(uv python find "$PYTHON_VERSION")"
PYTHON_HOME="$(dirname "$(dirname "$PYTHON_BIN")")"
cp -R "$PYTHON_HOME" "$SIDECAR_DIR/python"

uv venv --python "$PYTHON_BIN" "$TMP_VENV"
uv pip install --python "$TMP_VENV/bin/python" "$ROOT"

SITE_PACKAGES="$(find "$TMP_VENV" -maxdepth 4 -type d -name site-packages | head -1)"
cp -R "$SITE_PACKAGES" "$SIDECAR_DIR/site-packages"

rm -rf "$TMP_VENV"

echo "sidecar 构建完成: $SIDECAR_DIR"
echo "Python: $(find "$SIDECAR_DIR/python" -name 'python3*' -type f | head -1)"
