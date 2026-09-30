#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$ROOT_DIR/.venv/bin/python" ]; then
    "$ROOT_DIR/.venv/bin/python" "$SCRIPT_DIR/start_demo.py" "$@"
else
    python3 "$SCRIPT_DIR/start_demo.py" "$@"
fi
