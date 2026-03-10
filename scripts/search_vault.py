#!/usr/bin/env python3
"""CLI tool to search and explore the WhatsApp YouTube Vault."""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ANTHROPIC_API_KEY", "placeholder")

from pipeline.vault import get_recent, get_stats, init_db, search


def print_entry(entry: dict) -> None:
    """Pretty-print a single vault entry.

    Args:
        entry: A dict representing a vault row.
    """
    print(f"  [{entry['group_name']}] {entry['title']}")
    print(f"    Channel: {entry['channel']}  |  Category: {entry['category']}")
    print(f"    URL: {entry['url']}")
    print(f"    Processed: {entry['processed_at']}")
    print()


def cmd_search(args: argparse.Namespace) -> None:
    """Execute a full-text search.

    Args:
        args: Parsed CLI arguments.
    """
    results = search(args.query, group=args.group, limit=args.limit)
    if not results:
        print("No results found.")
        return
    print(f"Found {len(results)} result(s):\n")
    for entry in results:
        print_entry(entry)


def cmd_stats(args: argparse.Namespace) -> None:
    """Display vault statistics.

    Args:
        args: Parsed CLI arguments (unused).
    """
    stats = get_stats()
    print(f"Total videos: {stats['total']}\n")
    if stats["by_group"]:
        print("By group:")
        for group, count in stats["by_group"].items():
            print(f"  {group}: {count}")
        print()
    if stats["by_category"]:
        print("By category:")
        for cat, count in stats["by_category"].items():
            print(f"  {cat}: {count}")


def cmd_recent(args: argparse.Namespace) -> None:
    """Show the most recent entries.

    Args:
        args: Parsed CLI arguments.
    """
    entries = get_recent(limit=args.recent)
    if not entries:
        print("Vault is empty.")
        return
    print(f"Recent {len(entries)} entries:\n")
    for entry in entries:
        print_entry(entry)


def main() -> None:
    """Parse arguments and dispatch to the appropriate command."""
    parser = argparse.ArgumentParser(
        description="Search and explore the WhatsApp YouTube Vault"
    )
    parser.add_argument("query", nargs="?", help="Full-text search query")
    parser.add_argument("--group", help="Filter by group name")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--stats", action="store_true", help="Show vault statistics")
    parser.add_argument("--recent", type=int, metavar="N", help="Show N most recent entries")

    args = parser.parse_args()

    init_db()

    if args.stats:
        cmd_stats(args)
    elif args.recent:
        cmd_recent(args)
    elif args.query:
        cmd_search(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
