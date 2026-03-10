# WhatsApp YouTube Vault

An automated pipeline that monitors WhatsApp groups, extracts YouTube links, fetches transcripts and metadata, summarizes each video via Claude API, and stores everything in a categorized knowledge vault (SQLite + Markdown).

---

## Requirements

- **Node.js** >= 18
- **Python** >= 3.11
- **An Anthropic API key** ([get one here](https://console.anthropic.com/))

---

## Environment Setup

### 1. Clone and enter the project

```bash
cd whatsapp-youtube-vault
```

### 2. Install Node.js dependencies

```bash
cd whatsapp-monitor
npm install
cd ..
```

### 3. Create a Python virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
CLAUDE_MODEL=claude-sonnet-4-20250514
VAULT_DIR=./vault
DATA_DIR=./data
LOG_LEVEL=INFO
```

### 5. Create required directories

```bash
mkdir -p vault/Elephanta vault/XEconomics vault/G-Lab data
```

### 6. Initialize the SQLite database

```bash
python3 -c "
import sys, os
sys.path.insert(0, '.')
os.environ.setdefault('ANTHROPIC_API_KEY', 'placeholder')
from pipeline.vault import init_db
from pathlib import Path
init_db(Path('vault/vault.db'))
"
```

> **Or run everything at once:**
>
> ```bash
> bash scripts/setup.sh
> ```
>
> This script verifies prerequisites, installs all dependencies, creates directories, initializes the database, and copies `.env.example` to `.env` if needed.

---

## Running the Application

### Terminal 1 — Start the WhatsApp Monitor

```bash
cd whatsapp-monitor
node src/monitor.js
```

On the first run, scan the QR code displayed in your terminal with WhatsApp. The session persists after that.

Or use the helper script:

```bash
bash scripts/run_monitor.sh
```

### Terminal 2 — Start the Python Pipeline

```bash
source .venv/bin/activate
python3 -m pipeline.watcher
```

The pipeline watches `data/links.jsonl` for new entries and processes them automatically.

Or use the helper script:

```bash
bash scripts/run_pipeline.sh
```

---

## Architecture

```
WhatsApp Web --> whatsapp-web.js (Node.js) --> links.jsonl
                      |
                      +-- QR auth, persistent session, 3 target groups

links.jsonl --> Python Pipeline (main orchestrator)
                      |
                      +-- 1. Parse & validate (Pydantic v2)
                      +-- 2. Fetch YouTube metadata (yt-dlp)
                      +-- 3. Fetch transcript (youtube-transcript-api)
                      +-- 4. Summarize via Claude API (anthropic SDK)
                      +-- 5. Categorize (group -> default category, LLM override)
                      +-- 6. Store (SQLite + Markdown vault)
```

---

## Target Groups

| Group Name  | Default Category | Domain                              |
|-------------|------------------|--------------------------------------|
| Elephanta   | Geopolitics      | World affairs, diplomacy, conflict   |
| XEconomics  | Finance          | Markets, macro, crypto, policy       |
| G-Lab       | AI/Technology    | ML, LLMs, research, software        |

---

## Searching the Vault

```bash
# Full-text search
python scripts/search_vault.py "AI regulation"

# Filter by group
python scripts/search_vault.py "trade war" --group Elephanta

# Vault statistics
python scripts/search_vault.py --stats

# Recent entries
python scripts/search_vault.py --recent 10
```

---

## Project Structure

```
whatsapp-youtube-vault/
├── .env.example                # Environment variable template
├── .gitignore
├── README.md
├── requirements.txt            # Python dependencies
├── whatsapp-monitor/           # Node.js WhatsApp client
│   ├── package.json
│   └── src/
│       └── monitor.js          # WhatsApp Web listener
├── pipeline/                   # Python processing pipeline
│   ├── __init__.py
│   ├── config.py               # Settings & env vars
│   ├── models.py               # Pydantic v2 models
│   ├── youtube_extractor.py    # Metadata & transcript fetching
│   ├── summarizer.py           # Claude API summarization
│   ├── vault.py                # SQLite + Markdown storage
│   ├── processor.py            # Pipeline orchestrator
│   └── watcher.py              # File watcher for links.jsonl
├── scripts/                    # Setup & utility scripts
│   ├── setup.sh                # One-command setup
│   ├── run_monitor.sh          # Start WhatsApp monitor
│   ├── run_pipeline.sh         # Start Python pipeline
│   └── search_vault.py         # CLI search tool
├── tests/                      # pytest test suite
│   ├── __init__.py
│   ├── test_extractor.py
│   ├── test_models.py
│   ├── test_summarizer.py
│   └── test_vault.py
├── vault/                      # Generated knowledge base (gitignored)
│   ├── Elephanta/
│   ├── XEconomics/
│   └── G-Lab/
└── data/                       # Runtime data (gitignored)
    └── links.jsonl
```

---

## Running Tests

```bash
cd whatsapp-youtube-vault
source .venv/bin/activate
pytest tests/ -v
```

All external APIs (YouTube, Anthropic) are mocked in tests.

## How It Works

1. **WhatsApp Monitor** (`monitor.js`) listens for messages in the three target groups via `whatsapp-web.js`.
2. When a message contains YouTube URLs, it extracts them and appends a JSON line to `data/links.jsonl`.
3. **Pipeline Watcher** (`watcher.py`) polls the JSONL file for new entries.
4. For each new entry, the **Processor** (`processor.py`) runs:
   - **Validation** — Pydantic v2 models validate the raw JSON.
   - **Deduplication** — Already-processed video IDs are skipped (checked against SQLite).
   - **Metadata** — `yt-dlp` fetches title, channel, duration, view count, etc.
   - **Transcript** — `youtube-transcript-api` fetches the video transcript.
   - **Summarization** — Claude API generates a structured summary (overview, key points, takeaways, category, tags).
   - **Storage** — The result is stored in both SQLite (with FTS5 full-text search) and as a Markdown file in the `vault/` directory.

---