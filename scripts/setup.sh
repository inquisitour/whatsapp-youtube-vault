#!/bin/bash
set -e

echo "=== WhatsApp YouTube Vault — Setup ==="
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed. Please install Node.js >= 18."
    exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "ERROR: Node.js >= 18 required (found v$(node -v))"
    exit 1
fi
echo "Node.js: $(node -v) ✓"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed. Please install Python >= 3.11."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.minor}")')
PY_MAJOR=$(python3 -c 'import sys; print(f"{sys.version_info.major}")')
if [ "$PY_MAJOR" -lt 3 ] || [ "$PY_VERSION" -lt 11 ]; then
    echo "ERROR: Python >= 3.11 required (found $(python3 --version))"
    exit 1
fi
echo "Python:  $(python3 --version) ✓"
echo ""

# Project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Install Node.js dependencies
echo "Installing Node.js dependencies..."
cd whatsapp-monitor && npm install && cd ..
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt
echo ""

# Create directories
echo "Creating directories..."
mkdir -p vault/Elephanta vault/XEconomics vault/G-Lab data
echo ""

# Initialize SQLite DB
echo "Initializing database..."
python3 -c "
import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault('ANTHROPIC_API_KEY', 'placeholder')
from pipeline.vault import init_db
from pathlib import Path
init_db(Path('vault/vault.db'))
"
echo ""

# Copy .env if needed
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — please edit it with your API key."
else
    echo ".env already exists."
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your ANTHROPIC_API_KEY"
echo "  2. Start the WhatsApp monitor:  bash scripts/run_monitor.sh"
echo "  3. Start the Python pipeline:   bash scripts/run_pipeline.sh"
