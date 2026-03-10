"""Storage layer — SQLite database and Markdown vault files."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path

from pipeline.config import get_settings
from pipeline.models import VaultEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

_CREATE_VIDEOS_TABLE = """\
CREATE TABLE IF NOT EXISTS videos (
    video_id            TEXT PRIMARY KEY,
    url                 TEXT NOT NULL,
    group_name          TEXT NOT NULL,
    sender              TEXT NOT NULL,
    message_id          TEXT NOT NULL,
    title               TEXT NOT NULL,
    channel             TEXT NOT NULL,
    duration_seconds    INTEGER NOT NULL,
    view_count          INTEGER NOT NULL DEFAULT 0,
    upload_date         TEXT,
    tags                TEXT NOT NULL DEFAULT '[]',
    transcript_text     TEXT NOT NULL,
    transcript_method   TEXT NOT NULL,
    transcript_word_count INTEGER NOT NULL DEFAULT 0,
    summary_overview    TEXT NOT NULL,
    key_points          TEXT NOT NULL DEFAULT '[]',
    takeaways           TEXT NOT NULL DEFAULT '[]',
    category            TEXT NOT NULL,
    processed_at        TEXT NOT NULL,
    processing_started_at TEXT,
    processing_time_seconds REAL
);
"""

_CREATE_FTS_TABLE = """\
CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts USING fts5(
    title,
    channel,
    transcript_text,
    summary_overview,
    tags,
    content='videos',
    content_rowid='rowid'
);
"""

_CREATE_FTS_INSERT_TRIGGER = """\
CREATE TRIGGER IF NOT EXISTS videos_ai AFTER INSERT ON videos BEGIN
    INSERT INTO videos_fts(rowid, title, channel, transcript_text, summary_overview, tags)
    VALUES (new.rowid, new.title, new.channel, new.transcript_text, new.summary_overview, new.tags);
END;
"""

_CREATE_FTS_DELETE_TRIGGER = """\
CREATE TRIGGER IF NOT EXISTS videos_ad AFTER DELETE ON videos BEGIN
    INSERT INTO videos_fts(videos_fts, rowid, title, channel, transcript_text, summary_overview, tags)
    VALUES ('delete', old.rowid, old.title, old.channel, old.transcript_text, old.summary_overview, old.tags);
END;
"""


def _get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection to the vault SQLite database.

    Args:
        db_path: Override path (for testing). Defaults to config.

    Returns:
        An open ``sqlite3.Connection``.
    """
    if db_path is None:
        db_path = get_settings().db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create the database tables and FTS5 indexes if they don't exist.

    Args:
        db_path: Override path (for testing).
    """
    conn = _get_connection(db_path)
    try:
        conn.execute(_CREATE_VIDEOS_TABLE)
        conn.execute(_CREATE_FTS_TABLE)
        conn.execute(_CREATE_FTS_INSERT_TRIGGER)
        conn.execute(_CREATE_FTS_DELETE_TRIGGER)
        conn.commit()
        logger.info("Database initialized at %s", db_path or get_settings().db_path)
    finally:
        conn.close()


def store(entry: VaultEntry, db_path: Path | None = None) -> None:
    """Store a ``VaultEntry`` in both SQLite and Markdown.

    Args:
        entry: The fully-processed vault entry.
        db_path: Override DB path (for testing).
    """
    _store_sqlite(entry, db_path)
    _store_markdown(entry)


def _store_sqlite(entry: VaultEntry, db_path: Path | None = None) -> None:
    """Insert or replace a vault entry in SQLite.

    Args:
        entry: The vault entry.
        db_path: Override path.
    """
    conn = _get_connection(db_path)
    try:
        # Delete first so the trigger fires for FTS cleanup
        conn.execute("DELETE FROM videos WHERE video_id = ?", (entry.video_id,))
        conn.execute(
            """\
            INSERT INTO videos (
                video_id, url, group_name, sender, message_id,
                title, channel, duration_seconds, view_count, upload_date, tags,
                transcript_text, transcript_method, transcript_word_count,
                summary_overview, key_points, takeaways, category,
                processed_at, processing_started_at, processing_time_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.video_id,
                entry.url,
                entry.group_name.value,
                entry.sender,
                entry.message_id,
                entry.title,
                entry.channel,
                entry.duration_seconds,
                entry.view_count,
                entry.upload_date,
                json.dumps(entry.tags),
                entry.transcript_text,
                entry.transcript_method,
                entry.transcript_word_count,
                entry.summary_overview,
                json.dumps(entry.key_points),
                json.dumps(entry.takeaways),
                entry.category.value,
                entry.processed_at,
                entry.processing_started_at,
                entry.processing_time_seconds,
            ),
        )
        conn.commit()
        logger.info("Stored %s in SQLite", entry.video_id)
    finally:
        conn.close()


def _sanitize_filename(title: str) -> str:
    """Sanitize a video title for use as a filename.

    Args:
        title: Raw video title.

    Returns:
        A lowercase, hyphenated, filesystem-safe string (max 80 chars).
    """
    name = title.lower()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"[\s]+", "-", name).strip("-")
    return name[:80]


def _store_markdown(entry: VaultEntry) -> None:
    """Write a Markdown file for the vault entry.

    Args:
        entry: The vault entry.
    """
    settings = get_settings()
    group_dir = Path(settings.vault_dir) / entry.group_name.value
    group_dir.mkdir(parents=True, exist_ok=True)

    date_prefix = entry.processed_at[:10]  # YYYY-MM-DD
    safe_title = _sanitize_filename(entry.title)
    filename = f"{date_prefix}_{safe_title}.md"
    filepath = group_dir / filename

    key_points_md = "\n".join(f"- {kp}" for kp in entry.key_points)
    takeaways_md = "\n".join(f"- {t}" for t in entry.takeaways)
    tags_str = ", ".join(entry.tags)

    content = f"""\
---
video_id: {entry.video_id}
title: "{entry.title}"
url: {entry.url}
channel: "{entry.channel}"
duration: {entry.duration_seconds}
category: {entry.category.value}
tags: [{tags_str}]
processed: {entry.processed_at}
---

# {entry.title}

## Overview

{entry.summary_overview}

## Key Points

{key_points_md}

## Takeaways

{takeaways_md}

## Source

- **Channel:** {entry.channel}
- **URL:** {entry.url}
- **Duration:** {entry.duration_seconds}s
- **Views:** {entry.view_count:,}
- **Group:** {entry.group_name.value}
- **Sender:** {entry.sender}
"""

    filepath.write_text(content, encoding="utf-8")
    logger.info("Wrote Markdown to %s", filepath)


def is_processed(video_id: str, db_path: Path | None = None) -> bool:
    """Check whether a video has already been processed.

    Args:
        video_id: The YouTube video ID.
        db_path: Override path.

    Returns:
        ``True`` if the video exists in the database.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def search(
    query: str,
    group: str | None = None,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[dict]:
    """Full-text search across the vault.

    Args:
        query: The search query (FTS5 MATCH syntax).
        group: Optional group name filter.
        limit: Max results.
        db_path: Override path.

    Returns:
        List of matching rows as dicts.
    """
    conn = _get_connection(db_path)
    try:
        sql = """\
            SELECT v.* FROM videos v
            JOIN videos_fts f ON v.rowid = f.rowid
            WHERE videos_fts MATCH ?
        """
        params: list = [query]

        if group:
            sql += " AND v.group_name = ?"
            params.append(group)

        sql += " ORDER BY v.processed_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stats(db_path: Path | None = None) -> dict:
    """Return vault statistics.

    Args:
        db_path: Override path.

    Returns:
        Dict with total count and breakdowns by group and category.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]

        by_group = {}
        for row in conn.execute(
            "SELECT group_name, COUNT(*) as cnt FROM videos GROUP BY group_name"
        ):
            by_group[row["group_name"]] = row["cnt"]

        by_category = {}
        for row in conn.execute(
            "SELECT category, COUNT(*) as cnt FROM videos GROUP BY category"
        ):
            by_category[row["category"]] = row["cnt"]

        return {"total": total, "by_group": by_group, "by_category": by_category}
    finally:
        conn.close()


def get_recent(limit: int = 10, db_path: Path | None = None) -> list[dict]:
    """Return the most recently processed entries.

    Args:
        limit: Number of entries to return.
        db_path: Override path.

    Returns:
        List of rows as dicts, most recent first.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM videos ORDER BY processed_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
