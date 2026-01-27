"""Fetch YouTube video captions/transcript. No API key required."""

import re

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from common URL forms. Returns None if not recognised."""
    url = (url or "").strip()
    if not url:
        return None
    # youtu.be/VIDEO_ID
    m = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
    if m:
        return m.group(1)
    # youtube.com/watch?v=VIDEO_ID or /v/VIDEO_ID
    m = re.search(r"(?:v=|/v/)([a-zA-Z0-9_-]{11})", url)
    if m:
        return m.group(1)
    return None


def get_transcript(youtube_url: str) -> str:
    """
    Fetch transcript for the given YouTube URL.
    Returns plain text (captions joined with spaces).
    Raises ValueError with a user-friendly message if fetch fails.
    """
    video_id = extract_video_id(youtube_url)
    if not video_id:
        raise ValueError("Not a valid YouTube URL. Use a link like https://www.youtube.com/watch?v=... or https://youtu.be/...")

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
    except Exception as e:
        err = str(e).lower()
        if "disabled" in err or "transcript" in err and "not" in err:
            raise ValueError("This video has captions/transcript disabled.") from e
        if "unavailable" in err or "private" in err:
            raise ValueError("Video is unavailable or private.") from e
        if "no transcript" in err or "not found" in err:
            raise ValueError("No transcript available for this video (language or format).") from e
        raise ValueError(f"Could not fetch transcript: {e}") from e

    if not fetched:
        raise ValueError("Transcript was empty.")

    # FetchedTranscript is iterable; each item has .text
    text = " ".join(snippet.text for snippet in fetched if getattr(snippet, "text", None))
    return text.strip() or " "
