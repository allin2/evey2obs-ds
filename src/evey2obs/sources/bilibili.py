"""B站 (Bilibili) platform adapter.

Uses B站 public API for metadata (no cookies required).
Uses /x/player/playurl for audio streams (no cookies required).
Falls back to yt-dlp for subtitle extraction.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

import httpx

from evey2obs.models import (
    ContentType,
    ExtractedText,
    ExtractionMethod,
    ResolvedSource,
    Segment,
    SourceInput,
    SourceMetadata,
    SourceType,
    TemporaryMedia,
)
from evey2obs.settings import AppSettings
from evey2obs.sources.base import YtDlpAdapter

logger = logging.getLogger(__name__)

_BVID_RE = re.compile(r"BV[a-zA-Z0-9]{10}")
_BILI_API = "https://api.bilibili.com"


class BilibiliAdapter(YtDlpAdapter):
    """Adapter for B站 video content.

    All extraction uses B站 public APIs — no cookies or login required.
    """

    def __init__(self, settings: AppSettings) -> None:
        super().__init__(
            settings=settings,
            source_type=SourceType.BILIBILI,
            domains=["bilibili.com", "www.bilibili.com", "b23.tv"],
            subtitle_langs=["zh-Hans", "zh-CN", "zh", "en"],
            auto_subs=False,
        )
        self._client: httpx.AsyncClient | None = None

    # ── resolve ──────────────────────────────────────────────────────────

    async def resolve(self, source_input: SourceInput) -> ResolvedSource:
        url = self._extract_matching_url(source_input)
        canonical = await self._resolve_b23(url)
        return ResolvedSource(
            source_type=SourceType.BILIBILI,
            content_type=ContentType.VIDEO,
            canonical_url=canonical,
            source_id=self._extract_source_id(canonical),
        )

    # ── metadata (public API) ────────────────────────────────────────────

    async def extract_metadata(self, source: ResolvedSource) -> SourceMetadata:
        data = await self._bili_get("/x/web-interface/view", {"bvid": source.source_id})
        if data and data.get("code") == 0:
            info = data["data"]
            pub_ts = info.get("pubdate", 0)
            return SourceMetadata(
                title=info.get("title") or None,
                author=(info.get("owner") or {}).get("name") or None,
                published_at=datetime.fromtimestamp(pub_ts, tz=UTC) if pub_ts else None,
                duration_seconds=info.get("duration"),
                description=info.get("desc") or None,
            )
        return await super().extract_metadata(source)

    # ── subtitles ────────────────────────────────────────────────────────

    async def extract_text(self, source: ResolvedSource) -> ExtractedText | None:
        cid = await self._get_cid(source.source_id)
        if cid:
            player = await self._bili_get(
                "/x/player/wbi/v2", {"bvid": source.source_id, "cid": cid}
            )
            if player and player.get("code") == 0:
                sub_list = (
                    player.get("data", {}).get("subtitle", {}).get("subtitles", [])
                )
                if sub_list:
                    sub_url = ""
                    for s in sub_list:
                        if "中文" in s.get("lan_doc", ""):
                            sub_url = s.get("subtitle_url", "")
                            break
                    if not sub_url:
                        sub_url = sub_list[0].get("subtitle_url", "")
                    if sub_url:
                        if sub_url.startswith("//"):
                            sub_url = "https:" + sub_url
                        segs = await self._download_json_sub(sub_url)
                        if segs:
                            return ExtractedText(
                                text=" ".join(s.text for s in segs),
                                segments=tuple(segs),
                                extraction_method=ExtractionMethod.SUBTITLE,
                            )
        return await super().extract_text(source)

    # ── media (playurl API, no cookies) ──────────────────────────────────

    async def extract_media(self, source: ResolvedSource) -> TemporaryMedia | None:
        cid = await self._get_cid(source.source_id)
        if not cid:
            return await super().extract_media(source)

        playurl = await self._bili_get(
            "/x/player/playurl",
            {
                "bvid": source.source_id,
                "cid": cid,
                "qn": "0",
                "fnval": "16",
                "fnver": "0",
                "fourk": "1",
                "platform": "web",
            },
        )
        if not playurl or playurl.get("code") != 0:
            return await super().extract_media(source)

        dash = playurl.get("data", {}).get("dash", {})
        audio_tracks = dash.get("audio", [])
        if audio_tracks:
            best = max(audio_tracks, key=lambda t: t.get("bandwidth", 0))
            audio_url = best.get("baseUrl") or best.get("base_url", "")
            if audio_url:
                return await self._download_audio(audio_url, source.source_id)

        durl = playurl.get("data", {}).get("durl", [])
        if durl:
            video_url = durl[0].get("url", "")
            if video_url:
                return await self._download_audio(video_url, source.source_id)

        return None

    # ── helpers ──────────────────────────────────────────────────────────

    def _extract_source_id(self, canonical_url: str) -> str:
        m = _BVID_RE.search(canonical_url)
        if m:
            return m.group(0)
        parts = canonical_url.rstrip("/").split("/")
        return parts[-1] if parts else canonical_url

    async def _resolve_b23(self, url: str) -> str:
        if _BVID_RE.search(url):
            return url
        client = await self._get_client()
        try:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=False,
                timeout=10.0,
            )
            if 300 <= resp.status_code < 400:
                loc = resp.headers.get("Location", "")
                bv = _BVID_RE.search(loc)
                if bv:
                    return f"https://www.bilibili.com/video/{bv.group(0)}"
                return loc
        except Exception:
            pass
        return await self._resolve_url(url)

    async def _get_cid(self, bvid: str) -> int | None:
        data = await self._bili_get("/x/player/pagelist", {"bvid": bvid})
        if data and data.get("code") == 0 and data.get("data"):
            return data["data"][0].get("cid")
        return None

    async def _bili_get(self, path: str, params: dict) -> dict | None:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{_BILI_API}{path}",
                params=params,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36"
                    ),
                    "Referer": "https://www.bilibili.com",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.debug("B站 API %s failed: %s", path, exc)
            return None

    async def _download_json_sub(self, url: str) -> list[Segment]:
        client = await self._get_client()
        try:
            resp = await client.get(url, timeout=15.0, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []
        segments: list[Segment] = []
        for entry in data.get("body", []):
            s, e, t = entry.get("from", 0), entry.get("to", 0), entry.get("content", "")
            if t.strip():
                segments.append(Segment(start=float(s), end=float(e), text=t))
        return segments

    async def _download_audio(
        self, url: str, source_id: str
    ) -> TemporaryMedia | None:
        try:
            client = await self._get_client()
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36"
                    ),
                    "Referer": "https://www.bilibili.com",
                },
                timeout=120.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            dest = self._temp_dir / f"{source_id}_audio.m4a"
            dest.write_bytes(resp.content)
            return TemporaryMedia(file_path=str(dest), media_type="audio/m4a")
        except Exception as exc:
            logger.warning("B站 audio download failed: %s", exc)
            return None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client
