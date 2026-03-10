#!/bin/bash
# Start the Python pipeline watcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
echo "Starting pipeline watcher..."
python3 -m pipeline.watcher
