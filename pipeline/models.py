"""Pydantic v2 models for every pipeline boundary."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WhatsAppGroup(str, Enum):
    """Supported WhatsApp group names."""

    ELEPHANTA = "Elephanta"
    XECONOMICS = "XEconomics"
    GLAB = "G-Lab"


class ContentCategory(str, Enum):
    """Content categories for vault entries."""

    GEOPOLITICS = "Geopolitics"
    FINANCE = "Finance"
    AI_TECH = "AI/Technology"
    EDUCATION = "Education"
    OTHER = "Other"


GROUP_CATEGORY_MAP: dict[WhatsAppGroup, ContentCategory] = {
    WhatsAppGroup.ELEPHANTA: ContentCategory.GEOPOLITICS,
    WhatsAppGroup.XECONOMICS: ContentCategory.FINANCE,
    WhatsAppGroup.GLAB: ContentCategory.AI_TECH,
}

# ---------------------------------------------------------------------------
# YouTube URL / video-id helpers
# ---------------------------------------------------------------------------

VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")

YOUTUBE_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|music\.youtube\.com)"
)

VIDEO_ID_EXTRACT = re.compile(
    r"(?:v=|youtu\.be/|shorts/|embed/|v/)([a-zA-Z0-9_-]{11})"
)


# ---------------------------------------------------------------------------
# 1. RawLinkEntry — parsed directly from links.jsonl
# ---------------------------------------------------------------------------

class RawLinkEntry(BaseModel):
    """A single line from ``links.jsonl`` written by the WhatsApp monitor."""

    model_config = ConfigDict()

    timestamp: str
    group_name: WhatsAppGroup
    sender: str
    youtube_urls: list[str] = Field(min_length=1)
    message_text: str
    message_id: str

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Ensure the timestamp is valid ISO 8601."""
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


# ---------------------------------------------------------------------------
# 2. YouTubeLink — validated single YouTube URL with video_id extraction
# ---------------------------------------------------------------------------

class YouTubeLink(BaseModel):
    """A validated YouTube URL with its extracted video ID."""

    model_config = ConfigDict(strict=True)

    url: str
    video_id: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """URL must match a known YouTube domain pattern."""
        if not YOUTUBE_URL_PATTERN.match(v):
            raise ValueError(f"Not a YouTube URL: {v}")
        return v

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, v: str) -> str:
        """Video ID must be exactly 11 valid characters."""
        if not VIDEO_ID_PATTERN.match(v):
            raise ValueError(
                f"Invalid video ID '{v}' — must be 11 chars [a-zA-Z0-9_-]"
            )
        return v

    @classmethod
    def from_url(cls, url: str) -> "YouTubeLink":
        """Construct a ``YouTubeLink`` by extracting the video ID from *url*."""
        match = VIDEO_ID_EXTRACT.search(url)
        if not match:
            raise ValueError(f"Cannot extract video ID from URL: {url}")
        return cls(url=url, video_id=match.group(1))


# ---------------------------------------------------------------------------
# 3. VideoMetadata — enriched data from yt-dlp
# ---------------------------------------------------------------------------

class VideoMetadata(BaseModel):
    """Metadata about a YouTube video fetched via yt-dlp."""

    model_config = ConfigDict()

    video_id: str
    title: str
    channel: str
    duration_seconds: int = Field(ge=0)
    view_count: int = Field(ge=0, default=0)
    upload_date: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    thumbnail_url: Optional[str] = None

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, v: str) -> str:
        """Video ID must be exactly 11 valid characters."""
        if not VIDEO_ID_PATTERN.match(v):
            raise ValueError(f"Invalid video ID '{v}'")
        return v


# ---------------------------------------------------------------------------
# 4. TranscriptResult — fetched transcript text
# ---------------------------------------------------------------------------

class TranscriptResult(BaseModel):
    """Result of fetching a video transcript."""

    model_config = ConfigDict()

    video_id: str
    text: str = Field(min_length=1)
    method: str = Field(description="How the transcript was obtained, e.g. 'youtube-transcript-api'")
    language: str = "en"
    word_count: int = 0

    @model_validator(mode="after")
    def compute_word_count(self) -> "TranscriptResult":
        """Auto-compute word_count from text."""
        self.word_count = len(self.text.split())
        return self


# ---------------------------------------------------------------------------
# 5. VideoSummary — LLM-generated summary
# ---------------------------------------------------------------------------

class VideoSummary(BaseModel):
    """Summary of a video produced by Claude."""

    model_config = ConfigDict()

    overview: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1, max_length=10)
    takeaways: list[str] = Field(min_length=1, max_length=10)
    category: ContentCategory
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 6. VaultEntry — final combined record for storage
# ---------------------------------------------------------------------------

class VaultEntry(BaseModel):
    """Complete record combining all pipeline outputs, ready for storage."""

    model_config = ConfigDict()

    video_id: str
    url: str
    group_name: WhatsAppGroup
    sender: str
    message_id: str

    # Metadata
    title: str
    channel: str
    duration_seconds: int = Field(ge=0)
    view_count: int = Field(ge=0, default=0)
    upload_date: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    # Transcript
    transcript_text: str
    transcript_method: str
    transcript_word_count: int = Field(ge=0)

    # Summary
    summary_overview: str
    key_points: list[str] = Field(min_length=1, max_length=10)
    takeaways: list[str] = Field(min_length=1, max_length=10)
    category: ContentCategory

    # Timing
    processed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    processing_started_at: Optional[str] = None
    processing_time_seconds: Optional[float] = None

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, v: str) -> str:
        """Video ID must be exactly 11 valid characters."""
        if not VIDEO_ID_PATTERN.match(v):
            raise ValueError(f"Invalid video ID '{v}'")
        return v

    @model_validator(mode="after")
    def compute_processing_time(self) -> "VaultEntry":
        """Compute processing_time_seconds if both timestamps are present."""
        if self.processing_started_at and self.processed_at:
            start = datetime.fromisoformat(self.processing_started_at)
            end = datetime.fromisoformat(self.processed_at)
            self.processing_time_seconds = (end - start).total_seconds()
        return self
