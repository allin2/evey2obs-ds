"""Tests for XiaohongshuAdapter — fixture-based, no real network."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from evey2obs.errors import Evey2ObsError
from evey2obs.models import ContentType, ErrorCode, SourceInput, SourceType
from evey2obs.protocols import SourceAdapter
from evey2obs.settings import AppSettings
from evey2obs.sources.xiaohongshu import XiaohongshuAdapter

# Sample INITIAL_STATE for image-note
MOCK_STATE_IMAGE = {
    "note": {
        "noteId": "abc123def456",
        "type": "normal",
        "title": "Test Image Note",
        "desc": "Description text for image note",
        "user": {"nickname": "TestUser"},
        "imageList": [
            {"urlDefault": "https://ci.xiaohongshu.com/photo.jpg"},
            {"url": "https://ci.xiaohongshu.com/photo2.jpg"},
        ],
    }
}

MOCK_STATE_VIDEO = {
    "note": {
        "noteId": "vid123",
        "type": "video",
        "title": "Test Video Note",
        "desc": "Video description",
        "user": {"nickname": "VideoUser"},
        "video": {
            "media": {
                "stream": {
                    "h264": [{"masterUrl": "https://sns-video-qc.xhscdn.com/video.mp4"}]
                }
            }
        },
    }
}


def _make_html(initial_state: dict) -> str:
    """Wrap a dict as a window.__INITIAL_STATE__ script tag."""
    json_str = json.dumps(initial_state, ensure_ascii=False)
    return f'<html><script>window.__INITIAL_STATE__ = {json_str}</script></html>'


@pytest.fixture
def xhs_adapter() -> XiaohongshuAdapter:
    return XiaohongshuAdapter(AppSettings())


# ── Protocol ────────────────────────────────────────────────────────────────


class TestProtocolCompliance:
    def test_implements_source_adapter_protocol(self, xhs_adapter: XiaohongshuAdapter) -> None:
        assert isinstance(xhs_adapter, SourceAdapter)


# ── CanHandle ───────────────────────────────────────────────────────────────


class TestCanHandle:
    def test_xhslink_short_link(self, xhs_adapter: XiaohongshuAdapter) -> None:
        si = SourceInput.from_urls(["https://xhslink.com/abc123"])
        assert xhs_adapter.can_handle(si)

    def test_xiaohongshu_full_url(self, xhs_adapter: XiaohongshuAdapter) -> None:
        si = SourceInput.from_urls(["https://www.xiaohongshu.com/discovery/item/abc"])
        assert xhs_adapter.can_handle(si)

    def test_douyin_url_false(self, xhs_adapter: XiaohongshuAdapter) -> None:
        si = SourceInput.from_urls(["https://v.douyin.com/abc/"])
        assert not xhs_adapter.can_handle(si)


# ── URL Sanitization ────────────────────────────────────────────────────────


class TestUrlSanitization:
    def test_preserves_xsec_token_and_type(self) -> None:
        url = "https://www.xiaohongshu.com/discovery/item/abc?xsec_token=SECRET&type=video&share_id=TRACK&appuid=USER"
        clean = XiaohongshuAdapter._sanitize_url(url)
        assert "xsec_token=SECRET" in clean
        assert "type=video" in clean
        assert "share_id" not in clean
        assert "appuid" not in clean

    def test_no_relevant_params(self) -> None:
        url = "https://www.xiaohongshu.com/discovery/item/abc"
        clean = XiaohongshuAdapter._sanitize_url(url)
        assert clean == url


# ── Source ID ───────────────────────────────────────────────────────────────


class TestSourceId:
    def test_extracts_from_discovery_path(self, xhs_adapter: XiaohongshuAdapter) -> None:
        sid = xhs_adapter._extract_source_id(
            "https://www.xiaohongshu.com/discovery/item/abc123def456"
        )
        assert sid == "abc123def456"

    def test_extracts_from_explore_path(self, xhs_adapter: XiaohongshuAdapter) -> None:
        sid = xhs_adapter._extract_source_id(
            "https://www.xiaohongshu.com/explore/note456"
        )
        assert sid == "note456"


# ── Content Type Detection ─────────────────────────────────────────────────


class TestContentTypeDetection:
    @pytest.mark.asyncio
    async def test_video_from_ytdlp_duration(self, xhs_adapter: XiaohongshuAdapter) -> None:
        with patch.object(xhs_adapter, "_run_ytdlp") as mock_ytdlp:
            mock_ytdlp.return_value = json.dumps({"duration": 30.0, "title": "Video"})
            ct = await xhs_adapter._detect_content_type("https://xhslink.com/test")
            assert ct == ContentType.VIDEO

    @pytest.mark.asyncio
    async def test_image_note_from_initial_state(self, xhs_adapter: XiaohongshuAdapter) -> None:
        with patch.object(
                xhs_adapter, "_run_ytdlp",
                side_effect=Evey2ObsError(code=ErrorCode.CONTENT_UNAVAILABLE, message="fail")
            ), patch.object(xhs_adapter, "_fetch_initial_state") as mock_fetch:
            mock_fetch.return_value = MOCK_STATE_IMAGE
            ct = await xhs_adapter._detect_content_type("https://xhslink.com/test")
            assert ct == ContentType.IMAGE_NOTE

    @pytest.mark.asyncio
    async def test_video_from_initial_state_fallback(self, xhs_adapter: XiaohongshuAdapter) -> None:
        with patch.object(
                xhs_adapter, "_run_ytdlp",
                side_effect=Evey2ObsError(code=ErrorCode.CONTENT_UNAVAILABLE, message="fail")
            ), patch.object(xhs_adapter, "_fetch_initial_state") as mock_fetch:
            mock_fetch.return_value = MOCK_STATE_VIDEO
            ct = await xhs_adapter._detect_content_type("https://xhslink.com/test")
            assert ct == ContentType.VIDEO


# ── Resolve ─────────────────────────────────────────────────────────────────


class TestResolve:
    @pytest.mark.asyncio
    async def test_missing_token_raises(self, xhs_adapter: XiaohongshuAdapter) -> None:
        with patch.object(xhs_adapter, "_resolve_xhs_url") as mock_resolve:
            mock_resolve.return_value = "https://www.xiaohongshu.com/discovery/item/abc"
            with pytest.raises(Exception) as exc_info:
                await xhs_adapter.resolve(SourceInput.from_urls(["https://xhslink.com/test"]))
            from evey2obs.errors import Evey2ObsError
            if isinstance(exc_info.value, Evey2ObsError):
                assert exc_info.value.code == ErrorCode.SHARE_TOKEN_MISSING

    @pytest.mark.asyncio
    async def test_resolve_video(self, xhs_adapter: XiaohongshuAdapter) -> None:
        with patch.object(xhs_adapter, "_resolve_xhs_url") as mock_resolve:
            mock_resolve.return_value = (
                "https://www.xiaohongshu.com/discovery/item/abc123?xsec_token=TOK&type=video"
            )
            with patch.object(xhs_adapter, "_detect_content_type", return_value=ContentType.VIDEO):
                result = await xhs_adapter.resolve(
                    SourceInput.from_urls(["https://xhslink.com/test"])
                )
                assert result.source_type == SourceType.XIAOHONGSHU
                assert result.content_type == ContentType.VIDEO
                assert "xsec_token" in result.canonical_url

    @pytest.mark.asyncio
    async def test_resolve_image_note(self, xhs_adapter: XiaohongshuAdapter) -> None:
        with patch.object(xhs_adapter, "_resolve_xhs_url") as mock_resolve:
            mock_resolve.return_value = (
                "https://www.xiaohongshu.com/discovery/item/abc123?xsec_token=TOK&type=normal"
            )
            with patch.object(
                xhs_adapter, "_detect_content_type", return_value=ContentType.IMAGE_NOTE
            ):
                result = await xhs_adapter.resolve(
                    SourceInput.from_urls(["https://xhslink.com/test"])
                )
                assert result.content_type == ContentType.IMAGE_NOTE


# ── Extract Text ────────────────────────────────────────────────────────────


class TestExtractText:
    @pytest.mark.asyncio
    async def test_image_note_extracts_description(
        self, xhs_adapter: XiaohongshuAdapter
    ) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.XIAOHONGSHU,
            content_type=ContentType.IMAGE_NOTE,
            canonical_url="https://www.xiaohongshu.com/discovery/item/abc123",
            source_id="abc123",
        )
        with patch.object(xhs_adapter, "_fetch_initial_state") as mock_fetch:
            mock_fetch.return_value = MOCK_STATE_IMAGE
            result = await xhs_adapter.extract_text(rs)
            assert result is not None
            assert result.text == "Description text for image note"

    @pytest.mark.asyncio
    async def test_image_note_populates_images(
        self, xhs_adapter: XiaohongshuAdapter
    ) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.XIAOHONGSHU,
            content_type=ContentType.IMAGE_NOTE,
            canonical_url="https://www.xiaohongshu.com/discovery/item/abc123",
            source_id="abc123",
        )
        with patch.object(xhs_adapter, "_fetch_initial_state") as mock_fetch, \
             patch.object(xhs_adapter, "_download_image") as mock_dl:
            mock_fetch.return_value = MOCK_STATE_IMAGE
            # Return a Path so images are included
            from pathlib import Path
            mock_dl.side_effect = lambda url: Path(f"/tmp/img_{hash(url) & 0xFF}.jpg")

            result = await xhs_adapter.extract_text(rs)
            assert result is not None
            assert len(result.images) == 2
            assert result.images[0].url == "https://ci.xiaohongshu.com/photo.jpg"


# ── Extract Metadata ────────────────────────────────────────────────────────


class TestExtractMetadata:
    @pytest.mark.asyncio
    async def test_falls_back_to_initial_state(
        self, xhs_adapter: XiaohongshuAdapter
    ) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.XIAOHONGSHU,
            content_type=ContentType.IMAGE_NOTE,
            canonical_url="https://www.xiaohongshu.com/discovery/item/abc123",
            source_id="abc123",
        )
        # Make super().extract_metadata() fail, fallback to INITIAL_STATE
        with patch.object(
                xhs_adapter, "_run_ytdlp",
                side_effect=Evey2ObsError(code=ErrorCode.CONTENT_UNAVAILABLE, message="fail")
            ), patch.object(xhs_adapter, "_fetch_initial_state") as mock_fetch:
            mock_fetch.return_value = MOCK_STATE_IMAGE
            result = await xhs_adapter.extract_metadata(rs)
            assert result.title == "Test Image Note"
            assert result.author == "TestUser"


# ── Token Missing ───────────────────────────────────────────────────────────


class TestTokenMissing:
    @pytest.mark.asyncio
    async def test_no_token_raises(self, xhs_adapter: XiaohongshuAdapter) -> None:
        with patch.object(xhs_adapter, "_run_ytdlp") as mock_run:
            # Resolved URL lacks xsec_token
            mock_run.return_value = "https://www.xiaohongshu.com/discovery/item/abc"
            from evey2obs.errors import Evey2ObsError

            with pytest.raises(Evey2ObsError) as exc_info:
                await xhs_adapter.resolve(
                    SourceInput.from_urls(["https://xhslink.com/test"])
                )
            assert exc_info.value.code == ErrorCode.SHARE_TOKEN_MISSING
