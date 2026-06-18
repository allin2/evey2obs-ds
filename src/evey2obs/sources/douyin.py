"""抖音 (Douyin) platform adapter."""

from __future__ import annotations

import re

from evey2obs.models import SourceType
from evey2obs.settings import AppSettings
from evey2obs.sources.base import YtDlpAdapter

_DOUYIN_ID_RE = re.compile(r"/video/(\d+)")


class DouyinAdapter(YtDlpAdapter):
    """Adapter for 抖音 (Douyin) short video content.

    Supports v.douyin.com short links, douyin.com/video URLs, and
    whole-sentence share text.  Audio-first strategy: subtitle if
    available, otherwise audio + Whisper fallback.
    """

    def __init__(self, settings: AppSettings) -> None:
        super().__init__(
            settings=settings,
            source_type=SourceType.DOUYIN,
            domains=["douyin.com", "www.douyin.com", "v.douyin.com"],
            subtitle_langs=["zh-Hans", "zh-CN", "zh"],
            auto_subs=False,
        )

    def _extract_source_id(self, canonical_url: str) -> str:
        """Extract numeric video ID from Douyin URL."""
        m = _DOUYIN_ID_RE.search(canonical_url)
        if m:
            return m.group(1)
        # Fallback: last path segment
        parts = canonical_url.rstrip("/").split("/")
        return parts[-1] if parts else canonical_url
