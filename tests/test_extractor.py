"""Tests for YouTube metadata and transcript extraction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pipeline.models import YouTubeLink
from pipeline.youtube_extractor import get_metadata, get_transcript


# ---------------------------------------------------------------------------
# URL regex / video_id extraction (via YouTubeLink.from_url)
# ---------------------------------------------------------------------------


class TestVideoIdExtraction:
    """Test video_id extraction from all YouTube URL variants."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/v/dQw4w9WgXcQ",
            "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        ],
    )
    def test_all_url_variants(self, url: str) -> None:
        """All standard YouTube URL variants extract the correct video_id."""
        link = YouTubeLink.from_url(url)
        assert link.video_id == "dQw4w9WgXcQ"

    def test_url_with_extra_params(self) -> None:
        """URLs with extra query parameters still extract video_id."""
        link = YouTubeLink.from_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120&list=PLabc"
        )
        assert link.video_id == "dQw4w9WgXcQ"

    def test_non_youtube_url_fails(self) -> None:
        """Non-YouTube URLs raise ValueError."""
        with pytest.raises(ValueError):
            YouTubeLink.from_url("https://vimeo.com/12345678")


# ---------------------------------------------------------------------------
# get_metadata (mocked yt-dlp)
# ---------------------------------------------------------------------------


class TestGetMetadata:
    """Tests for get_metadata with mocked yt-dlp."""

    @patch("pipeline.youtube_extractor.yt_dlp.YoutubeDL")
    def test_metadata_parsing(self, mock_ydl_class: MagicMock) -> None:
        """Metadata is correctly parsed from yt-dlp info dict."""
        mock_info = {
            "id": "dQw4w9WgXcQ",
            "title": "Never Gonna Give You Up",
            "channel": "Rick Astley",
            "duration": 212,
            "view_count": 1_500_000_000,
            "upload_date": "20091025",
            "description": "Official video",
            "tags": ["music", "pop"],
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        }

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl_class.return_value = mock_ydl

        meta = get_metadata("https://youtube.com/watch?v=dQw4w9WgXcQ")

        assert meta.video_id == "dQw4w9WgXcQ"
        assert meta.title == "Never Gonna Give You Up"
        assert meta.channel == "Rick Astley"
        assert meta.duration_seconds == 212
        assert meta.view_count == 1_500_000_000
        assert "music" in meta.tags

    @patch("pipeline.youtube_extractor.yt_dlp.YoutubeDL")
    def test_metadata_missing_fields(self, mock_ydl_class: MagicMock) -> None:
        """Missing optional fields get sensible defaults."""
        mock_info = {
            "id": "dQw4w9WgXcQ",
            "title": "Test",
            "channel": None,
            "uploader": "Fallback Uploader",
            "duration": None,
            "view_count": None,
        }

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl_class.return_value = mock_ydl

        meta = get_metadata("https://youtube.com/watch?v=dQw4w9WgXcQ")

        assert meta.channel == "Fallback Uploader"
        assert meta.duration_seconds == 0
        assert meta.view_count == 0


# ---------------------------------------------------------------------------
# get_transcript (mocked youtube-transcript-api)
# ---------------------------------------------------------------------------


class TestGetTranscript:
    """Tests for get_transcript with mocked youtube-transcript-api."""

    @patch("pipeline.youtube_extractor.YouTubeTranscriptApi")
    def test_transcript_success(self, mock_api_class: MagicMock) -> None:
        """Successful transcript fetch returns a TranscriptResult."""
        snippet1 = MagicMock()
        snippet1.text = "Hello world"
        snippet2 = MagicMock()
        snippet2.text = "this is a test"

        mock_result = MagicMock()
        mock_result.snippets = [snippet1, snippet2]
        mock_result.language = "en"

        mock_api = MagicMock()
        mock_api.fetch.return_value = mock_result
        mock_api_class.return_value = mock_api

        result = get_transcript("dQw4w9WgXcQ")

        assert result is not None
        assert result.text == "Hello world this is a test"
        assert result.method == "youtube-transcript-api"
        assert result.word_count == 6

    @patch("pipeline.youtube_extractor.YouTubeTranscriptApi")
    def test_transcript_failure_returns_none(self, mock_api_class: MagicMock) -> None:
        """When the API raises, get_transcript returns None."""
        mock_api = MagicMock()
        mock_api.fetch.side_effect = Exception("No transcript")
        mock_api_class.return_value = mock_api

        result = get_transcript("dQw4w9WgXcQ")
        assert result is None
