"""Fetch YouTube video metadata and transcripts."""

from __future__ import annotations

import logging

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from pipeline.models import TranscriptResult, VideoMetadata

logger = logging.getLogger(__name__)


def get_metadata(url: str) -> VideoMetadata:
    """Fetch video metadata via yt-dlp (no download).

    Args:
        url: A YouTube video URL.

    Returns:
        A validated ``VideoMetadata`` instance.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return VideoMetadata(
        video_id=info.get("id", ""),
        title=info.get("title", "Unknown"),
        channel=info.get("channel") or info.get("uploader") or "Unknown",
        duration_seconds=int(info.get("duration", 0) or 0),
        view_count=int(info.get("view_count", 0) or 0),
        upload_date=info.get("upload_date"),
        description=info.get("description"),
        tags=info.get("tags") or [],
        thumbnail_url=info.get("thumbnail"),
    )


def get_transcript(video_id: str) -> TranscriptResult | None:
    """Fetch the transcript for a YouTube video.

    Uses the youtube-transcript-api v1.0+ instance-based API.  Returns
    ``None`` if no transcript is available (Whisper fallback is not
    implemented).

    Args:
        video_id: The 11-character YouTube video ID.

    Returns:
        A ``TranscriptResult`` or ``None`` on failure.
    """
    try:
        ytt = YouTubeTranscriptApi()
        result = ytt.fetch(video_id)
        text = " ".join([snippet.text for snippet in result.snippets])

        if not text.strip():
            logger.warning("Empty transcript for video %s", video_id)
            return None

        language = "en"
        if hasattr(result, "language"):
            language = result.language or "en"

        return TranscriptResult(
            video_id=video_id,
            text=text,
            method="youtube-transcript-api",
            language=language,
        )
    except Exception as exc:
        logger.warning("Transcript unavailable for %s: %s", video_id, exc)
        return None
