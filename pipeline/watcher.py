"""File watcher — polls ``links.jsonl`` for new entries and processes them."""

from __future__ import annotations

import json
import logging
import os
import time

from rich.console import Console

from pipeline.config import get_settings
from pipeline.processor import process_link

logger = logging.getLogger(__name__)
console = Console()

POLL_INTERVAL = 5  # seconds


def watch_loop() -> None:
    """Poll ``links.jsonl`` every few seconds for new entries.

    Tracks the file read position so only new lines are processed.
    """
    settings = get_settings()
    links_file = str(settings.links_file)

    console.print(f"[bold]Watching:[/bold] {links_file}")
    console.print(f"[bold]Poll interval:[/bold] {POLL_INTERVAL}s")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    last_position = 0

    # If the file already exists, skip to the end so we don't reprocess
    if os.path.exists(links_file):
        last_position = os.path.getsize(links_file)
        console.print(f"[dim]Skipping existing content ({last_position} bytes)[/dim]")

    while True:
        try:
            if os.path.exists(links_file) and os.path.getsize(links_file) > last_position:
                with open(links_file, encoding="utf-8") as f:
                    f.seek(last_position)
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            process_link(entry)
                        except json.JSONDecodeError as exc:
                            logger.error("Invalid JSON line: %s", exc)
                        except Exception as exc:
                            logger.error("Error processing entry: %s", exc)
                    last_position = f.tell()
        except Exception as exc:
            logger.error("Watcher error: %s", exc)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        watch_loop()
    except KeyboardInterrupt:
        console.print("\n[bold]Watcher stopped.[/bold]")
