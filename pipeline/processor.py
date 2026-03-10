"""Main pipeline orchestrator — process raw link entries end-to-end."""

from __future__ import annotations

import logging
from datetime import datetime

from rich.console import Console

from pipeline.models import (
    GROUP_CATEGORY_MAP,
    RawLinkEntry,
    VaultEntry,
    YouTubeLink,
)
from pipeline.summarizer import summarize
from pipeline.vault import init_db, is_processed, store
from pipeline.youtube_extractor import get_metadata, get_transcript

logger = logging.getLogger(__name__)
console = Console()


def process_link(raw_entry: dict) -> list[VaultEntry]:
    """Run the full pipeline for one link entry from ``links.jsonl``.

    Steps for each YouTube URL in the entry:
        1. Validate raw entry -> ``RawLinkEntry``
        2. Deduplicate (skip already-processed video IDs)
        3. Extract video_id -> ``YouTubeLink``
        4. Fetch metadata -> ``VideoMetadata``
        5. Fetch transcript -> ``TranscriptResult``
        6. Summarize -> ``VideoSummary``
        7. Combine -> ``VaultEntry``
        8. Store (SQLite + Markdown)

    Args:
        raw_entry: A dict parsed from one JSON line.

    Returns:
        List of successfully processed ``VaultEntry`` objects.
    """
    # Ensure DB is ready
    init_db()

    # Step 1: validate
    try:
        entry = RawLinkEntry(**raw_entry)
    except Exception as exc:
        console.print(f"[red]Validation failed:[/red] {exc}")
        logger.error("Failed to validate raw entry: %s", exc)
        return []

    console.print(
        f"\n[bold cyan]Processing {len(entry.youtube_urls)} link(s) "
        f"from {entry.group_name.value}[/bold cyan]"
    )

    results: list[VaultEntry] = []
    default_category = GROUP_CATEGORY_MAP.get(entry.group_name)

    for url in entry.youtube_urls:
        started_at = datetime.utcnow().isoformat()

        # Step 2: extract video_id
        try:
            yt_link = YouTubeLink.from_url(url)
        except Exception as exc:
            console.print(f"  [yellow]Skipping URL {url}: {exc}[/yellow]")
            logger.warning("Bad URL %s: %s", url, exc)
            continue

        # Step 3: deduplication
        if is_processed(yt_link.video_id):
            console.print(f"  [dim]Already processed: {yt_link.video_id}[/dim]")
            continue

        console.print(f"  [green]Processing:[/green] {yt_link.video_id}")

        # Step 4: metadata
        try:
            metadata = get_metadata(url)
            console.print(f"    Metadata: {metadata.title}")
        except Exception as exc:
            console.print(f"    [red]Metadata failed:[/red] {exc}")
            logger.error("Metadata failed for %s: %s", url, exc)
            continue

        # Step 5: transcript
        try:
            transcript = get_transcript(yt_link.video_id)
            if transcript is None:
                console.print(f"    [yellow]No transcript available — skipping[/yellow]")
                continue
            console.print(f"    Transcript: {transcript.word_count} words")
        except Exception as exc:
            console.print(f"    [red]Transcript failed:[/red] {exc}")
            logger.error("Transcript failed for %s: %s", yt_link.video_id, exc)
            continue

        # Step 6: summarize
        try:
            summary = summarize(
                title=metadata.title,
                channel=metadata.channel,
                duration=metadata.duration_seconds,
                transcript=transcript.text,
                default_category=default_category,
            )
            console.print(f"    Summary: {summary.category.value}")
        except Exception as exc:
            console.print(f"    [red]Summarization failed:[/red] {exc}")
            logger.error("Summarize failed for %s: %s", yt_link.video_id, exc)
            continue

        # Step 7: combine into VaultEntry
        try:
            vault_entry = VaultEntry(
                video_id=yt_link.video_id,
                url=url,
                group_name=entry.group_name,
                sender=entry.sender,
                message_id=entry.message_id,
                title=metadata.title,
                channel=metadata.channel,
                duration_seconds=metadata.duration_seconds,
                view_count=metadata.view_count,
                upload_date=metadata.upload_date,
                tags=summary.tags,
                transcript_text=transcript.text,
                transcript_method=transcript.method,
                transcript_word_count=transcript.word_count,
                summary_overview=summary.overview,
                key_points=summary.key_points,
                takeaways=summary.takeaways,
                category=summary.category,
                processing_started_at=started_at,
            )
        except Exception as exc:
            console.print(f"    [red]VaultEntry creation failed:[/red] {exc}")
            logger.error("VaultEntry failed for %s: %s", yt_link.video_id, exc)
            continue

        # Step 8: store
        try:
            store(vault_entry)
            console.print(f"    [bold green]Stored![/bold green]")
            results.append(vault_entry)
        except Exception as exc:
            console.print(f"    [red]Storage failed:[/red] {exc}")
            logger.error("Store failed for %s: %s", yt_link.video_id, exc)
            continue

    console.print(
        f"[bold cyan]Done — {len(results)}/{len(entry.youtube_urls)} "
        f"videos processed[/bold cyan]"
    )
    return results
