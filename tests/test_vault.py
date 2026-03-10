"""Tests for vault storage — SQLite operations, Markdown generation, dedup."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline.models import ContentCategory, VaultEntry, WhatsAppGroup
from pipeline.vault import (
    _sanitize_filename,
    _store_markdown,
    _store_sqlite,
    get_stats,
    init_db,
    is_processed,
    search,
)


def _make_entry(**overrides) -> VaultEntry:
    """Create a VaultEntry with sensible defaults, overridable by kwargs."""
    defaults = {
        "video_id": "dQw4w9WgXcQ",
        "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "group_name": "Elephanta",
        "sender": "Alice",
        "message_id": "msg_123",
        "title": "Test Video Title",
        "channel": "Test Channel",
        "duration_seconds": 120,
        "view_count": 500,
        "transcript_text": "Hello world transcript text",
        "transcript_method": "youtube-transcript-api",
        "transcript_word_count": 4,
        "summary_overview": "A short overview.",
        "key_points": ["Point 1", "Point 2"],
        "takeaways": ["Takeaway 1"],
        "category": "Geopolitics",
        "processed_at": "2024-06-15T10:00:00",
        "processing_started_at": "2024-06-15T09:59:50",
    }
    defaults.update(overrides)
    return VaultEntry(**defaults)


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary database path and initialize it."""
    db_path = tmp_path / "test_vault.db"
    init_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------


class TestInitDb:
    """Tests for database initialization."""

    def test_creates_tables(self, tmp_db: Path) -> None:
        """init_db creates the videos and videos_fts tables."""
        conn = sqlite3.connect(str(tmp_db))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow')"
        ).fetchall()
        table_names = {t[0] for t in tables}
        conn.close()

        assert "videos" in table_names
        assert "videos_fts" in table_names

    def test_idempotent(self, tmp_db: Path) -> None:
        """Calling init_db twice doesn't raise."""
        init_db(tmp_db)  # second call


# ---------------------------------------------------------------------------
# Store and retrieve
# ---------------------------------------------------------------------------


class TestStoreAndRetrieve:
    """Tests for SQLite store, dedup, search, and stats."""

    def test_store_and_is_processed(self, tmp_db: Path) -> None:
        """Stored entries are detected by is_processed."""
        entry = _make_entry()
        _store_sqlite(entry, tmp_db)

        assert is_processed("dQw4w9WgXcQ", tmp_db) is True
        assert is_processed("nonexistent1", tmp_db) is False

    def test_store_deduplication(self, tmp_db: Path) -> None:
        """Storing the same video_id twice replaces the old entry."""
        entry1 = _make_entry(title="First Title")
        entry2 = _make_entry(title="Updated Title")

        _store_sqlite(entry1, tmp_db)
        _store_sqlite(entry2, tmp_db)

        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT title FROM videos WHERE video_id = ?", ("dQw4w9WgXcQ",)
        ).fetchone()
        conn.close()

        assert row["title"] == "Updated Title"

    def test_search_fts(self, tmp_db: Path) -> None:
        """Full-text search finds stored entries."""
        entry = _make_entry()
        _store_sqlite(entry, tmp_db)

        results = search("Hello world", db_path=tmp_db)
        assert len(results) >= 1
        assert results[0]["video_id"] == "dQw4w9WgXcQ"

    def test_search_with_group_filter(self, tmp_db: Path) -> None:
        """Group filter limits search results."""
        entry = _make_entry()
        _store_sqlite(entry, tmp_db)

        results = search("Hello", group="Elephanta", db_path=tmp_db)
        assert len(results) == 1

        results = search("Hello", group="G-Lab", db_path=tmp_db)
        assert len(results) == 0

    def test_get_stats(self, tmp_db: Path) -> None:
        """get_stats returns correct counts."""
        _store_sqlite(_make_entry(video_id="aaaaaaaaaaa"), tmp_db)
        _store_sqlite(
            _make_entry(video_id="bbbbbbbbbbb", group_name="G-Lab", category="AI/Technology"),
            tmp_db,
        )

        stats = get_stats(tmp_db)
        assert stats["total"] == 2
        assert stats["by_group"]["Elephanta"] == 1
        assert stats["by_group"]["G-Lab"] == 1


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------


class TestMarkdown:
    """Tests for Markdown file generation."""

    def test_markdown_file_created(self, tmp_path: Path) -> None:
        """_store_markdown creates a .md file in the correct group directory."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()

        mock_settings = type("S", (), {"vault_dir": str(vault_dir)})()

        with patch("pipeline.vault.get_settings", return_value=mock_settings):
            entry = _make_entry()
            _store_markdown(entry)

        md_files = list((vault_dir / "Elephanta").glob("*.md"))
        assert len(md_files) == 1

        content = md_files[0].read_text()
        assert "Test Video Title" in content
        assert "Point 1" in content
        assert "Takeaway 1" in content
        assert "video_id: dQw4w9WgXcQ" in content


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    """Tests for the _sanitize_filename helper."""

    def test_basic_sanitization(self) -> None:
        """Spaces become hyphens, special chars are removed."""
        assert _sanitize_filename("Hello World!") == "hello-world"

    def test_long_title_truncated(self) -> None:
        """Titles longer than 80 chars are truncated."""
        long_title = "a" * 200
        assert len(_sanitize_filename(long_title)) <= 80

    def test_special_characters(self) -> None:
        """Various special characters are stripped."""
        result = _sanitize_filename("What's the Deal? (Part 1) | Analysis")
        assert "'" not in result
        assert "(" not in result
        assert "|" not in result
