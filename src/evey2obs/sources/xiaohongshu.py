"""小红书 (Xiaohongshu) platform adapter.

Handles both video and image-note content types.  Preserves
``xsec_token`` and ``type`` parameters for extraction while
stripping tracking parameters from canonical URLs and cache keys.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from evey2obs.errors import Evey2ObsError
from evey2obs.models import (
    ContentType,
    ErrorCode,
    ExtractedText,
    ExtractionMethod,
    ImageRef,
    ResolvedSource,
    SourceInput,
    SourceMetadata,
    SourceType,
    TemporaryMedia,
)
from evey2obs.settings import AppSettings
from evey2obs.sources.base import YtDlpAdapter

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

# Parameters to preserve for extraction
_PRESERVE_PARAMS = {"xsec_token", "type"}

# Tracking parameters to always strip
_TRACKING_PARAMS = {
    "share_id", "shareRedId", "appuid", "share_channel", "share_source",
    "share_sign", "share_type", "source", "tracking_source",
}

# Pattern to find __INITIAL_STATE__ in HTML
_INITIAL_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>", re.DOTALL
)


# ── Adapter ─────────────────────────────────────────────────────────────────


class XiaohongshuAdapter(YtDlpAdapter):
    """Adapter for 小红书 (Xiaohongshu) video and image-note content.

    Supports xhslink.com short links and xiaohongshu.com full URLs.
    Uses yt-dlp as primary extractor with ``window.__INITIAL_STATE__``
    HTML parsing as fallback.
    """

    def __init__(self, settings: AppSettings) -> None:
        super().__init__(
            settings=settings,
            source_type=SourceType.XIAOHONGSHU,
            domains=["xiaohongshu.com", "www.xiaohongshu.com", "xhslink.com"],
            subtitle_langs=["zh-Hans", "zh-CN", "zh"],
            auto_subs=False,
        )
        self._http_client: httpx.AsyncClient | None = None

    # ── Protocol overrides ────────────────────────────────────────────────

    async def resolve(self, source_input: SourceInput) -> ResolvedSource:
        """Resolve short link, detect content type, sanitize URL."""
        url = self._extract_matching_url(source_input)

        # Resolve short link via HTTP redirect (yt-dlp doesn't support xhslink)
        try:
            canonical_raw = await self._resolve_xhs_url(url)
        except Evey2ObsError:
            raise
        except Exception as exc:
            raise Evey2ObsError(
                code=ErrorCode.SHARE_TOKEN_MISSING,
                message="Failed to resolve Xiaohongshu link. 请从小红书 App 重新复制分享链接",
                detail=str(exc),
                recoverable=True,
            ) from exc

        # Check for missing token
        if "xsec_token" not in canonical_raw:
            raise Evey2ObsError(
                code=ErrorCode.SHARE_TOKEN_MISSING,
                message="Share link missing access token. 请从小红书 App 重新复制分享链接",
                recoverable=True,
            )

        canonical = self._sanitize_url(canonical_raw)
        source_id = self._extract_source_id(canonical)

        # Detect content type
        content_type = await self._detect_content_type(canonical_raw)

        return ResolvedSource(
            source_type=SourceType.XIAOHONGSHU,
            content_type=content_type,
            canonical_url=canonical,
            source_id=source_id,
        )

    async def extract_metadata(self, source: ResolvedSource) -> SourceMetadata:
        """Fetch metadata via yt-dlp, falling back to INITIAL_STATE."""
        try:
            return await super().extract_metadata(source)
        except Evey2ObsError:
            return await self._extract_metadata_from_page(source)

    async def extract_text(self, source: ResolvedSource) -> ExtractedText | None:
        """Extract subtitles (video) or description (image-note)."""
        if source.content_type == ContentType.IMAGE_NOTE:
            return await self._extract_text_from_page(source)

        # For video: try subtitles first
        result = await super().extract_text(source)
        if result is not None:
            return result

        # Fallback: parse page for description
        page_text = await self._extract_text_from_page(source)
        return page_text

    async def extract_media(self, source: ResolvedSource) -> TemporaryMedia | None:
        """Download audio (video) or return None (image-note)."""
        if source.content_type == ContentType.IMAGE_NOTE:
            return None

        try:
            return await super().extract_media(source)
        except Evey2ObsError:
            return await self._extract_media_from_page(source)

    # ── URL resolution ────────────────────────────────────────────────────

    async def _resolve_xhs_url(self, url: str) -> str:
        """Resolve xhslink.com short link via HTTP redirect."""
        client = await self._get_client()
        try:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Linux; Android 12; Pixel 6) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Mobile Safari/537.36"
                    ),
                },
                follow_redirects=True,
                timeout=15.0,
            )
            return str(resp.url)
        except Exception:
            # Fallback to yt-dlp
            return await self._resolve_url(url)

    # ── Content type detection ─────────────────────────────────────────────

    async def _detect_content_type(self, url: str) -> ContentType:
        """Probe whether the note is a video or image-note."""
        # Try yt-dlp metadata first
        try:
            args = [url, "--dump-json", "--no-download", "--no-playlist"]
            stdout = await self._run_ytdlp(args, timeout=30)
            data = json.loads(stdout)
            if data.get("duration", 0) > 0:
                return ContentType.VIDEO
        except Evey2ObsError:
            pass

        # Fallback: parse INITIAL_STATE
        state = await self._fetch_initial_state(url)
        if state:
            note_type = state.get("note", {}).get("type", "")
            return ContentType.VIDEO if note_type == "video" else ContentType.IMAGE_NOTE

        return ContentType.IMAGE_NOTE  # default

    # ── INITIAL_STATE extraction ───────────────────────────────────────────

    async def _fetch_initial_state(self, url: str) -> dict | None:
        """GET the note page and parse window.__INITIAL_STATE__."""
        client = await self._get_client()
        try:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36"
                    ),
                },
                timeout=15.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            html = resp.text
        except Exception:
            return None

        m = _INITIAL_STATE_RE.search(html)
        if not m:
            return None

        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None

    async def _extract_metadata_from_page(self, source: ResolvedSource) -> SourceMetadata:
        """Parse metadata from INITIAL_STATE."""
        state = await self._fetch_initial_state(source.canonical_url)
        if not state:
            return SourceMetadata()

        note = state.get("note", {})
        user = note.get("user", {})
        return SourceMetadata(
            title=note.get("title"),
            author=user.get("nickname"),
            description=note.get("desc"),
        )

    async def _extract_text_from_page(self, source: ResolvedSource) -> ExtractedText:
        """Extract description text and images from INITIAL_STATE."""
        state = await self._fetch_initial_state(source.canonical_url)
        if not state:
            return ExtractedText(text="", extraction_method=ExtractionMethod.HTML)

        note = state.get("note", {})
        text = note.get("desc", "") or note.get("title", "") or ""

        # Download images for image-notes
        images: list[ImageRef] = []
        if source.content_type == ContentType.IMAGE_NOTE:
            image_list = note.get("imageList", [])
            for img_data in image_list:
                img_url = img_data.get("urlDefault") or img_data.get("url", "")
                if img_url:
                    local_path = await self._download_image(img_url)
                    if local_path:
                        images.append(
                            ImageRef(url=img_url, local_path=str(local_path))
                        )

        return ExtractedText(
            text=text,
            extraction_method=ExtractionMethod.HTML,
            images=tuple(images),
        )

    async def _extract_media_from_page(self, source: ResolvedSource) -> TemporaryMedia | None:
        """Download video media URL from INITIAL_STATE fallback."""
        state = await self._fetch_initial_state(source.canonical_url)
        if not state:
            return None

        note = state.get("note", {})
        video = note.get("video", {})
        media_info = video.get("media", {})
        streams = media_info.get("stream", {})
        h264 = streams.get("h264", [])

        if not h264:
            return None

        master_url = h264[0].get("masterUrl", "")
        if not master_url:
            return None

        # Download immediately (media URLs expire)
        local_path = self._temp_dir / f"{source.source_id}.mp4"
        try:
            client = await self._get_client()
            resp = await client.get(master_url, timeout=120.0, follow_redirects=True)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
            return TemporaryMedia(file_path=str(local_path), media_type="video/mp4")
        except Exception:
            return None

    # ── Image download ─────────────────────────────────────────────────────

    async def _download_image(self, url: str) -> Path | None:
        """Download an image immediately (URLs expire)."""
        try:
            client = await self._get_client()
            resp = await client.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()

            # Derive filename from URL or content-type
            suffix = ".jpg"
            content_type = resp.headers.get("content-type", "")
            if "png" in content_type:
                suffix = ".png"
            elif "webp" in content_type:
                suffix = ".webp"

            dest = self._temp_dir / f"img_{hash(url) & 0xFFFFFF:06x}{suffix}"
            dest.write_bytes(resp.content)
            return dest
        except Exception:
            return None

    # ── Token/URL sanitization ─────────────────────────────────────────────

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Remove tracking params from URL while keeping xsec_token and type."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Keep only preserve params
        clean_params = {
            k: v[0]
            for k, v in params.items()
            if k in _PRESERVE_PARAMS
        }

        return str(
            urlunparse(
                parsed._replace(
                    query=urlencode(clean_params, doseq=False) if clean_params else ""
                )
            )
        )

    def _extract_source_id(self, canonical_url: str) -> str:
        """Extract note ID from canonical URL path."""
        # Pattern: /discovery/item/{noteId} or /explore/{noteId}
        m = re.search(r"/(?:discovery/item|explore)/([a-zA-Z0-9]+)", canonical_url)
        if m:
            return m.group(1)
        parts = canonical_url.rstrip("/").split("/")
        return parts[-1] if parts else canonical_url

    # ── HTTP client ────────────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client
