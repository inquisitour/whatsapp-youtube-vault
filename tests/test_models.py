"""Tests for Pydantic v2 models — valid and invalid data."""

import pytest
from pydantic import ValidationError

from pipeline.models import (
    GROUP_CATEGORY_MAP,
    ContentCategory,
    RawLinkEntry,
    TranscriptResult,
    VaultEntry,
    VideoMetadata,
    VideoSummary,
    WhatsAppGroup,
    YouTubeLink,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    """Tests for enum values and GROUP_CATEGORY_MAP."""

    def test_whatsapp_group_values(self) -> None:
        """All expected group names are present."""
        assert WhatsAppGroup.ELEPHANTA.value == "Elephanta"
        assert WhatsAppGroup.XECONOMICS.value == "XEconomics"
        assert WhatsAppGroup.GLAB.value == "G-Lab"

    def test_content_category_values(self) -> None:
        """All expected category values are present."""
        assert ContentCategory.GEOPOLITICS.value == "Geopolitics"
        assert ContentCategory.FINANCE.value == "Finance"
        assert ContentCategory.AI_TECH.value == "AI/Technology"

    def test_group_category_mapping(self) -> None:
        """Default category mapping is correct."""
        assert GROUP_CATEGORY_MAP[WhatsAppGroup.ELEPHANTA] == ContentCategory.GEOPOLITICS
        assert GROUP_CATEGORY_MAP[WhatsAppGroup.XECONOMICS] == ContentCategory.FINANCE
        assert GROUP_CATEGORY_MAP[WhatsAppGroup.GLAB] == ContentCategory.AI_TECH


# ---------------------------------------------------------------------------
# RawLinkEntry
# ---------------------------------------------------------------------------


class TestRawLinkEntry:
    """Tests for RawLinkEntry model validation."""

    def _valid_data(self) -> dict:
        return {
            "timestamp": "2024-06-15T10:30:00",
            "group_name": "Elephanta",
            "sender": "Alice",
            "youtube_urls": ["https://youtube.com/watch?v=dQw4w9WgXcQ"],
            "message_text": "Check this out",
            "message_id": "msg_12345",
        }

    def test_valid_entry(self) -> None:
        """A well-formed entry validates correctly."""
        entry = RawLinkEntry(**self._valid_data())
        assert entry.group_name == WhatsAppGroup.ELEPHANTA
        assert len(entry.youtube_urls) == 1

    def test_invalid_group_name(self) -> None:
        """Unknown group names are rejected."""
        data = self._valid_data()
        data["group_name"] = "UnknownGroup"
        with pytest.raises(ValidationError):
            RawLinkEntry(**data)

    def test_empty_urls_rejected(self) -> None:
        """An empty youtube_urls list is rejected (min_length=1)."""
        data = self._valid_data()
        data["youtube_urls"] = []
        with pytest.raises(ValidationError):
            RawLinkEntry(**data)

    def test_invalid_timestamp(self) -> None:
        """A non-ISO timestamp is rejected."""
        data = self._valid_data()
        data["timestamp"] = "not-a-date"
        with pytest.raises(ValidationError):
            RawLinkEntry(**data)

    def test_z_suffix_timestamp(self) -> None:
        """ISO timestamps with Z suffix are accepted."""
        data = self._valid_data()
        data["timestamp"] = "2024-06-15T10:30:00Z"
        entry = RawLinkEntry(**data)
        assert entry.timestamp == "2024-06-15T10:30:00Z"


# ---------------------------------------------------------------------------
# YouTubeLink
# ---------------------------------------------------------------------------


class TestYouTubeLink:
    """Tests for YouTubeLink URL validation and video_id extraction."""

    def test_valid_link(self) -> None:
        """Standard watch URL validates and extracts video_id."""
        link = YouTubeLink(url="https://youtube.com/watch?v=dQw4w9WgXcQ", video_id="dQw4w9WgXcQ")
        assert link.video_id == "dQw4w9WgXcQ"

    def test_from_url_watch(self) -> None:
        """from_url works with standard watch URLs."""
        link = YouTubeLink.from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert link.video_id == "dQw4w9WgXcQ"

    def test_from_url_short(self) -> None:
        """from_url works with youtu.be short URLs."""
        link = YouTubeLink.from_url("https://youtu.be/dQw4w9WgXcQ")
        assert link.video_id == "dQw4w9WgXcQ"

    def test_from_url_shorts(self) -> None:
        """from_url works with /shorts/ URLs."""
        link = YouTubeLink.from_url("https://youtube.com/shorts/dQw4w9WgXcQ")
        assert link.video_id == "dQw4w9WgXcQ"

    def test_from_url_embed(self) -> None:
        """from_url works with /embed/ URLs."""
        link = YouTubeLink.from_url("https://www.youtube.com/embed/dQw4w9WgXcQ")
        assert link.video_id == "dQw4w9WgXcQ"

    def test_from_url_music(self) -> None:
        """from_url works with music.youtube.com URLs."""
        link = YouTubeLink.from_url("https://music.youtube.com/watch?v=dQw4w9WgXcQ")
        assert link.video_id == "dQw4w9WgXcQ"

    def test_invalid_url_rejected(self) -> None:
        """Non-YouTube URLs are rejected."""
        with pytest.raises(ValidationError):
            YouTubeLink(url="https://example.com/video", video_id="dQw4w9WgXcQ")

    def test_invalid_video_id_rejected(self) -> None:
        """Too-short video IDs are rejected."""
        with pytest.raises(ValidationError):
            YouTubeLink(url="https://youtube.com/watch?v=short", video_id="short")

    def test_from_url_bad_url(self) -> None:
        """from_url raises ValueError for non-extractable URLs."""
        with pytest.raises(ValueError):
            YouTubeLink.from_url("https://example.com")


# ---------------------------------------------------------------------------
# VideoMetadata
# ---------------------------------------------------------------------------


class TestVideoMetadata:
    """Tests for VideoMetadata model."""

    def test_valid_metadata(self) -> None:
        """Well-formed metadata validates correctly."""
        meta = VideoMetadata(
            video_id="dQw4w9WgXcQ",
            title="Test Video",
            channel="Test Channel",
            duration_seconds=120,
            view_count=1000,
        )
        assert meta.title == "Test Video"
        assert meta.tags == []

    def test_negative_duration_rejected(self) -> None:
        """Negative duration_seconds is rejected."""
        with pytest.raises(ValidationError):
            VideoMetadata(
                video_id="dQw4w9WgXcQ",
                title="T",
                channel="C",
                duration_seconds=-1,
            )


# ---------------------------------------------------------------------------
# TranscriptResult
# ---------------------------------------------------------------------------


class TestTranscriptResult:
    """Tests for TranscriptResult model and word count validator."""

    def test_word_count_computed(self) -> None:
        """word_count is auto-computed from text."""
        result = TranscriptResult(
            video_id="dQw4w9WgXcQ",
            text="hello world foo bar baz",
            method="youtube-transcript-api",
        )
        assert result.word_count == 5

    def test_empty_text_rejected(self) -> None:
        """Empty text is rejected (min_length=1)."""
        with pytest.raises(ValidationError):
            TranscriptResult(
                video_id="dQw4w9WgXcQ",
                text="",
                method="test",
            )


# ---------------------------------------------------------------------------
# VideoSummary
# ---------------------------------------------------------------------------


class TestVideoSummary:
    """Tests for VideoSummary model."""

    def test_valid_summary(self) -> None:
        """Well-formed summary validates."""
        summary = VideoSummary(
            overview="This is a test summary.",
            key_points=["Point 1", "Point 2"],
            takeaways=["Takeaway 1"],
            category=ContentCategory.AI_TECH,
            tags=["ai", "test"],
        )
        assert summary.category == ContentCategory.AI_TECH

    def test_empty_key_points_rejected(self) -> None:
        """Empty key_points list is rejected."""
        with pytest.raises(ValidationError):
            VideoSummary(
                overview="overview",
                key_points=[],
                takeaways=["t"],
                category=ContentCategory.OTHER,
            )

    def test_too_many_key_points_rejected(self) -> None:
        """More than 10 key_points is rejected."""
        with pytest.raises(ValidationError):
            VideoSummary(
                overview="overview",
                key_points=[f"Point {i}" for i in range(11)],
                takeaways=["t"],
                category=ContentCategory.OTHER,
            )


# ---------------------------------------------------------------------------
# VaultEntry
# ---------------------------------------------------------------------------


class TestVaultEntry:
    """Tests for VaultEntry model and processing time computation."""

    def _valid_data(self) -> dict:
        return {
            "video_id": "dQw4w9WgXcQ",
            "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "group_name": "Elephanta",
            "sender": "Alice",
            "message_id": "msg_123",
            "title": "Test Video",
            "channel": "Test Channel",
            "duration_seconds": 120,
            "view_count": 500,
            "transcript_text": "Hello world",
            "transcript_method": "youtube-transcript-api",
            "transcript_word_count": 2,
            "summary_overview": "A test video.",
            "key_points": ["Point 1"],
            "takeaways": ["Takeaway 1"],
            "category": "Geopolitics",
            "processing_started_at": "2024-06-15T10:00:00",
            "processed_at": "2024-06-15T10:00:05",
        }

    def test_valid_vault_entry(self) -> None:
        """A complete vault entry validates correctly."""
        entry = VaultEntry(**self._valid_data())
        assert entry.group_name == WhatsAppGroup.ELEPHANTA
        assert entry.category == ContentCategory.GEOPOLITICS

    def test_processing_time_computed(self) -> None:
        """processing_time_seconds is auto-computed from timestamps."""
        entry = VaultEntry(**self._valid_data())
        assert entry.processing_time_seconds == 5.0

    def test_invalid_video_id(self) -> None:
        """Invalid video IDs in VaultEntry are rejected."""
        data = self._valid_data()
        data["video_id"] = "bad"
        with pytest.raises(ValidationError):
            VaultEntry(**data)
