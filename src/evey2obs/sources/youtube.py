"""YouTube platform adapter."""

from __future__ import annotations

import re

from evey2obs.models import SourceType
from evey2obs.settings import AppSettings
from evey2obs.sources.base import YtDlpAdapter

# YouTube video ID: 11 characters of alphanumeric, -, _
_YOUTUBE_ID_RE = re.compile(r"[a-zA-Z0-9_-]{11}")


class YouTubeAdapter(YtDlpAdapter):
    """Adapter for YouTube video content.

    Uses yt-dlp for extraction.  Official and auto-generated subtitles
    preferred, audio + Whisper as fallback.
    """

    def __init__(self, settings: AppSettings) -> None:
        super().__init__(
            settings=settings,
            source_type=SourceType.YOUTUBE,
            domains=["youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"],
            subtitle_langs=["zh-Hans", "zh-CN", "zh", "en"],
            auto_subs=True,
        )

    def _extract_source_id(self, canonical_url: str) -> str:
        """Extract 11-character video ID from the canonical URL."""
        # Prefer match after v= or embed/
        m = re.search(r"(?:v=|/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})", canonical_url)
        if m:
            return m.group(1)
        # Fallback: any 11-char match
        m = _YOUTUBE_ID_RE.search(canonical_url)
        if m:
            return m.group(0)
        # Absolute fallback
        parts = canonical_url.rstrip("/").split("/")
        return parts[-1] or canonical_url
