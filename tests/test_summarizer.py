"""Tests for the Claude API summarizer with mocked Anthropic client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pipeline.models import ContentCategory
from pipeline.summarizer import (
    _coerce_category,
    _parse_bullet_list,
    _parse_xml_tag,
    summarize,
)


# ---------------------------------------------------------------------------
# XML parsing helpers
# ---------------------------------------------------------------------------


class TestXmlParsing:
    """Tests for XML tag extraction and bullet list parsing."""

    def test_parse_xml_tag(self) -> None:
        """Correctly extracts content between XML tags."""
        text = "<overview>This is the overview.</overview>"
        assert _parse_xml_tag(text, "overview") == "This is the overview."

    def test_parse_xml_tag_multiline(self) -> None:
        """Handles multiline content within tags."""
        text = "<key_points>\n- Point 1\n- Point 2\n</key_points>"
        assert "Point 1" in _parse_xml_tag(text, "key_points")

    def test_parse_xml_tag_missing(self) -> None:
        """Returns empty string when tag is not found."""
        assert _parse_xml_tag("no tags here", "overview") == ""

    def test_parse_bullet_list(self) -> None:
        """Parses dash-prefixed bullet list."""
        text = "- First item\n- Second item\n- Third item"
        items = _parse_bullet_list(text)
        assert items == ["First item", "Second item", "Third item"]

    def test_parse_bullet_list_with_stars(self) -> None:
        """Parses star-prefixed bullet list."""
        text = "* Alpha\n* Beta"
        items = _parse_bullet_list(text)
        assert items == ["Alpha", "Beta"]

    def test_parse_bullet_list_empty_lines(self) -> None:
        """Skips empty lines in bullet lists."""
        text = "- A\n\n- B\n  \n- C"
        items = _parse_bullet_list(text)
        assert len(items) == 3


# ---------------------------------------------------------------------------
# Category coercion
# ---------------------------------------------------------------------------


class TestCategoryCoercion:
    """Tests for _coerce_category."""

    def test_exact_match(self) -> None:
        """Exact category strings are recognized."""
        assert _coerce_category("Geopolitics") == ContentCategory.GEOPOLITICS

    def test_case_insensitive(self) -> None:
        """Category matching is case-insensitive."""
        assert _coerce_category("finance") == ContentCategory.FINANCE
        assert _coerce_category("AI/TECHNOLOGY") == ContentCategory.AI_TECH

    def test_unknown_returns_other(self) -> None:
        """Unknown categories fall back to OTHER."""
        assert _coerce_category("random stuff") == ContentCategory.OTHER


# ---------------------------------------------------------------------------
# summarize() — fully mocked
# ---------------------------------------------------------------------------


class TestSummarize:
    """Tests for the summarize function with mocked API."""

    MOCK_RESPONSE_TEXT = """\
<overview>This video discusses the impact of AI on modern society.</overview>
<key_points>
- AI is transforming healthcare
- Machine learning enables better predictions
- Ethical concerns remain important
</key_points>
<takeaways>
- Stay informed about AI developments
- Consider ethical implications in AI projects
</takeaways>
<category>AI/Technology</category>
<tags>AI, machine learning, ethics, society</tags>
"""

    @patch("pipeline.summarizer.get_settings")
    @patch("pipeline.summarizer.anthropic.Anthropic")
    def test_summarize_returns_video_summary(
        self, mock_anthropic_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """summarize() parses the mocked API response into a VideoSummary."""
        mock_settings_obj = MagicMock()
        mock_settings_obj.anthropic_api_key = "sk-test"
        mock_settings_obj.claude_model = "claude-sonnet-4-20250514"
        mock_settings.return_value = mock_settings_obj

        mock_content_block = MagicMock()
        mock_content_block.text = self.MOCK_RESPONSE_TEXT

        mock_response = MagicMock()
        mock_response.content = [mock_content_block]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        summary = summarize(
            title="AI in Society",
            channel="Tech Channel",
            duration=600,
            transcript="AI is changing the world...",
        )

        assert summary.category == ContentCategory.AI_TECH
        assert len(summary.key_points) == 3
        assert len(summary.takeaways) == 2
        assert "AI" in summary.overview
        assert "AI" in summary.tags

    @patch("pipeline.summarizer.get_settings")
    @patch("pipeline.summarizer.anthropic.Anthropic")
    def test_summarize_uses_default_category(
        self, mock_anthropic_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """When the LLM returns OTHER, the default_category is used."""
        mock_settings_obj = MagicMock()
        mock_settings_obj.anthropic_api_key = "sk-test"
        mock_settings_obj.claude_model = "claude-sonnet-4-20250514"
        mock_settings.return_value = mock_settings_obj

        response_text = """\
<overview>Some overview text here.</overview>
<key_points>
- Point one
</key_points>
<takeaways>
- Takeaway one
</takeaways>
<category>Nonsense</category>
<tags>misc</tags>
"""
        mock_content_block = MagicMock()
        mock_content_block.text = response_text

        mock_response = MagicMock()
        mock_response.content = [mock_content_block]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        summary = summarize(
            title="Test",
            channel="Ch",
            duration=60,
            transcript="transcript",
            default_category=ContentCategory.FINANCE,
        )

        assert summary.category == ContentCategory.FINANCE
