"""Summarize YouTube video content using the Claude API."""

from __future__ import annotations

import logging
import re

import anthropic

from pipeline.config import get_settings
from pipeline.models import ContentCategory, VideoSummary

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an expert content analyst. You summarize YouTube video transcripts "
    "into structured, concise knowledge notes. Always respond using the exact XML "
    "tag format requested."
)

USER_PROMPT_TEMPLATE = """\
Summarize the following YouTube video transcript.

Title: {title}
Channel: {channel}
Duration: {duration} seconds

Transcript:
{transcript}

Respond using these XML tags exactly:
<overview>2-3 sentence overview of the video content</overview>
<key_points>
- Key point 1
- Key point 2
...
</key_points>
<takeaways>
- Takeaway 1
- Takeaway 2
...
</takeaways>
<category>One of: Geopolitics, Finance, AI/Technology, Education, Other</category>
<tags>comma, separated, tags</tags>
"""


def _parse_xml_tag(text: str, tag: str) -> str:
    """Extract the content between opening and closing XML tags.

    Args:
        text: The full response text.
        tag: The XML tag name.

    Returns:
        The stripped inner text, or an empty string if not found.
    """
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse_bullet_list(text: str) -> list[str]:
    """Parse a bullet-point list from text into a list of strings.

    Args:
        text: Text containing lines starting with ``-`` or ``*``.

    Returns:
        List of cleaned bullet strings.
    """
    items: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("-", "*")):
            cleaned = line.lstrip("-* ").strip()
            if cleaned:
                items.append(cleaned)
    return items


def _coerce_category(raw: str) -> ContentCategory:
    """Map the raw category string from the LLM to a ``ContentCategory``.

    Args:
        raw: The raw category string returned by the model.

    Returns:
        A valid ``ContentCategory`` enum value.
    """
    raw_lower = raw.strip().lower()
    for cat in ContentCategory:
        if cat.value.lower() == raw_lower:
            return cat
    return ContentCategory.OTHER


def summarize(
    title: str,
    channel: str,
    duration: int,
    transcript: str,
    default_category: ContentCategory | None = None,
) -> VideoSummary:
    """Summarize a video transcript using the Claude API.

    Args:
        title: Video title.
        channel: Channel name.
        duration: Duration in seconds.
        transcript: Full transcript text.
        default_category: Fallback category if the LLM returns an invalid one.

    Returns:
        A validated ``VideoSummary``.
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Truncate very long transcripts to stay within context limits
    max_chars = 80_000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n[transcript truncated]"

    prompt = USER_PROMPT_TEMPLATE.format(
        title=title,
        channel=channel,
        duration=duration,
        transcript=transcript,
    )

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text

    overview = _parse_xml_tag(text, "overview") or "No overview available."
    key_points = _parse_bullet_list(_parse_xml_tag(text, "key_points")) or [
        "No key points extracted."
    ]
    takeaways = _parse_bullet_list(_parse_xml_tag(text, "takeaways")) or [
        "No takeaways extracted."
    ]
    category = _coerce_category(_parse_xml_tag(text, "category"))
    if category == ContentCategory.OTHER and default_category:
        category = default_category

    raw_tags = _parse_xml_tag(text, "tags")
    tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else []

    return VideoSummary(
        overview=overview,
        key_points=key_points,
        takeaways=takeaways,
        category=category,
        tags=tags,
    )
