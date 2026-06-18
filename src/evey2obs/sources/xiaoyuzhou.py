"""小宇宙 (Xiaoyuzhou) podcast episode adapter.

Extracts episode metadata, show notes, and official transcripts.
Falls back to audio download + Whisper when no transcript is available.
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from bs4 import BeautifulSoup

from evey2obs.errors import Evey2ObsError
from evey2obs.models import (
    ContentType,
    ExtractedText,
    ExtractionMethod,
    ResolvedSource,
    SourceInput,
    SourceMetadata,
    SourceType,
)
from evey2obs.settings import AppSettings
from evey2obs.sources.base import YtDlpAdapter

logger = logging.getLogger(__name__)

# Next.js data pattern for Xiaoyuzhou
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', re.DOTALL
)


class XiaoyuzhouAdapter(YtDlpAdapter):
    """Adapter for 小宇宙 (Xiaoyuzhou) podcast episodes.

    Extends :class:`YtDlpAdapter` for audio download fallback.
    Prefers official transcripts or show notes from the episode page.
    """

    def __init__(self, settings: AppSettings) -> None:
        super().__init__(
            settings=settings,
            source_type=SourceType.XIAOYUZHOU,
            domains=["xiaoyuzhoufm.com", "www.xiaoyuzhoufm.com"],
            subtitle_langs=["zh-Hans", "zh-CN", "zh"],
            auto_subs=False,
        )
        self._http_client: httpx.AsyncClient | None = None

    # ── Protocol overrides ────────────────────────────────────────────────

    async def resolve(self, source_input: SourceInput) -> ResolvedSource:
        url = self._extract_matching_url(source_input)
        canonical = url  # Xiaoyuzhou URLs are already canonical
        source_id = self._extract_source_id(canonical)

        return ResolvedSource(
            source_type=SourceType.XIAOYUZHOU,
            content_type=ContentType.AUDIO,
            canonical_url=canonical,
            source_id=source_id,
        )

    async def extract_metadata(self, source: ResolvedSource) -> SourceMetadata:
        """Try yt-dlp first, then scrape episode page."""
        try:
            return await super().extract_metadata(source)
        except Evey2ObsError:
            return await self._scrape_metadata(source.canonical_url)

    async def extract_text(self, source: ResolvedSource) -> ExtractedText | None:
        """Scrape episode page for transcript or show notes.

        Returns None if only show notes (no transcript) — triggers Whisper fallback.
        """
        data = await self._scrape_episode_page(source.canonical_url)
        if not data:
            return None

        # If we found a transcript, return it
        transcript = data.get("transcript", "")
        if isinstance(transcript, str) and transcript.strip():
            return ExtractedText(
                text=transcript,
                extraction_method=ExtractionMethod.HTML,
            )

        # If only show notes, return None to trigger audio+Whisper
        return None

    # ── Source ID ─────────────────────────────────────────────────────────

    def _extract_source_id(self, canonical_url: str) -> str:
        """Extract episode ID from URL."""
        m = re.search(r"/episode/([a-zA-Z0-9]+)", canonical_url)
        if m:
            return m.group(1)
        parts = canonical_url.rstrip("/").split("/")
        return parts[-1] if parts else canonical_url

    # ── Page scraping ─────────────────────────────────────────────────────

    async def _scrape_episode_page(self, url: str) -> dict | None:
        """Scrape Xiaoyuzhou episode page for metadata, show notes, transcript."""
        client = await self._get_client()
        try:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                timeout=20.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            logger.warning("Failed to fetch Xiaoyuzhou page: %s", exc)
            return None

        # Try Next.js embedded data
        data = self._parse_next_data(html)
        if data:
            return data

        # Fallback: DOM scraping
        return self._scrape_dom(html)

    async def _scrape_metadata(self, url: str) -> SourceMetadata:
        """Scrape metadata from episode page."""
        data = await self._scrape_episode_page(url)
        if not data:
            return SourceMetadata()

        return SourceMetadata(
            title=data.get("title"),
            author=data.get("podcast_name"),
            description=data.get("show_notes"),
            duration_seconds=data.get("duration"),
        )

    # ── Parsing helpers ───────────────────────────────────────────────────

    @staticmethod
    def _parse_next_data(html: str) -> dict | None:
        """Parse __NEXT_DATA__ JSON from Xiaoyuzhou page."""
        m = _NEXT_DATA_RE.search(html)
        if not m:
            return None
        try:
            raw = json.loads(m.group(1))
        except json.JSONDecodeError:
            return None

        # Navigate Next.js props
        props = raw.get("props", {}).get("pageProps", {})
        episode = props.get("episode", {}) or props

        if not episode:
            return None

        return {
            "title": episode.get("title", ""),
            "podcast_name": episode.get("podcast", {}).get("title", "")
            or episode.get("podcastName", ""),
            "show_notes": episode.get("shownotes", "")
            or episode.get("description", ""),
            "transcript": episode.get("transcript", "")
            or episode.get("fullTranscript", ""),
            "duration": episode.get("duration"),
            "host": episode.get("host", ""),
        }

    @staticmethod
    def _scrape_dom(html: str) -> dict | None:
        """Fallback: scrape DOM for episode info."""
        soup = BeautifulSoup(html, "html.parser")

        # Try JSON-LD
        ld = soup.select_one('script[type="application/ld+json"]')
        if ld and ld.string:
            try:
                ld_data = json.loads(ld.string)
                return {
                    "title": ld_data.get("name", ""),
                    "show_notes": ld_data.get("description", ""),
                }
            except json.JSONDecodeError:
                pass

        # DOM fallback
        title = ""
        title_el = soup.select_one("h1") or soup.select_one("title")
        if title_el:
            title = title_el.get_text(strip=True)

        # Look for transcript section
        transcript = ""
        selectors = (".transcript", ".episode-transcript", "[class*=transcript]", "#transcript")
        for selector in selectors:
            el = soup.select_one(selector)
            if el:
                transcript = el.get_text(strip=True)
                break

        return {
            "title": title,
            "transcript": transcript,
        } if title or transcript else None

    # ── HTTP client ───────────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client
