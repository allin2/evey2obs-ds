"""Tests for BilibiliAdapter — fixture-based, no real network."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from evey2obs.models import ContentType, SourceInput, SourceType
from evey2obs.protocols import SourceAdapter
from evey2obs.settings import AppSettings
from evey2obs.sources.base import _parse_srt, _parse_vtt
from evey2obs.sources.bilibili import BilibiliAdapter


@pytest.fixture
def bilibili_adapter() -> BilibiliAdapter:
    return BilibiliAdapter(AppSettings())


class TestProtocolCompliance:
    def test_implements_source_adapter_protocol(self, bilibili_adapter: BilibiliAdapter) -> None:
        assert isinstance(bilibili_adapter, SourceAdapter)


class TestCanHandle:
    def test_bilibili_url_true(self, bilibili_adapter: BilibiliAdapter) -> None:
        si = SourceInput.from_urls(["https://www.bilibili.com/video/BV1xx411c7mD"])
        assert bilibili_adapter.can_handle(si)

    def test_b23_tv_true(self, bilibili_adapter: BilibiliAdapter) -> None:
        si = SourceInput.from_urls(["https://b23.tv/abcdef"])
        assert bilibili_adapter.can_handle(si)

    def test_youtube_url_false(self, bilibili_adapter: BilibiliAdapter) -> None:
        si = SourceInput.from_urls(["https://www.youtube.com/watch?v=abc12345678"])
        assert not bilibili_adapter.can_handle(si)

    def test_share_text_with_bilibili(self, bilibili_adapter: BilibiliAdapter) -> None:
        si = SourceInput(raw_text="看看这个 https://b23.tv/xyz")
        assert bilibili_adapter.can_handle(si)


class TestResolve:
    @pytest.mark.asyncio
    async def test_extracts_bv_id(self, bilibili_adapter: BilibiliAdapter) -> None:
        with patch.object(bilibili_adapter, "_run_ytdlp") as mock_run:
            mock_run.return_value = "https://www.bilibili.com/video/BV1xx411c7mD"
            si = SourceInput.from_urls(["https://b23.tv/abcdef"])
            result = await bilibili_adapter.resolve(si)
            assert result.source_type == SourceType.BILIBILI
            assert result.content_type == ContentType.VIDEO
            assert result.source_id == "BV1xx411c7mD"


class TestExtractMetadata:
    @pytest.mark.asyncio
    async def test_parses_metadata_json(self, bilibili_adapter: BilibiliAdapter) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.BILIBILI,
            content_type=ContentType.VIDEO,
            canonical_url="https://www.bilibili.com/video/BV1xx411c7mD",
            source_id="BV1xx411c7mD",
        )

        metadata_json = json.dumps({
            "title": "测试视频",
            "uploader": "UP主",
            "upload_date": "20260617",
            "duration": 120.0,
            "description": "描述",
        })

        with patch.object(bilibili_adapter, "_bili_get", return_value=None), \
             patch.object(bilibili_adapter, "_run_ytdlp", return_value=metadata_json):
            result = await bilibili_adapter.extract_metadata(rs)
            assert result.title == "测试视频"
            assert result.author == "UP主"
            assert result.duration_seconds == 120.0


class TestSubtitleParsing:
    def test_parse_vtt(self, tmp_path: Path) -> None:
        vtt = tmp_path / "test.vtt"
        vtt.write_text("""WEBVTT

00:00:01.000 --> 00:00:02.500
第一段字幕

00:00:03.000 --> 00:00:05.000
第二段字幕
""")
        segments = _parse_vtt(vtt)
        assert len(segments) == 2
        assert segments[0].start == 1.0
        assert segments[0].text == "第一段字幕"

    def test_parse_srt(self, tmp_path: Path) -> None:
        srt = tmp_path / "test.srt"
        srt.write_text("""1
00:00:01,000 --> 00:00:02,500
第一段字幕

2
00:00:03,000 --> 00:00:05,000
第二段字幕
""")
        segments = _parse_srt(srt)
        assert len(segments) == 2
        assert segments[0].start == 1.0
        assert segments[0].text == "第一段字幕"


class TestErrorMapping:
    @pytest.mark.asyncio
    async def test_403_error_maps_to_content_unavailable(
        self, bilibili_adapter: BilibiliAdapter
    ) -> None:
        from evey2obs.errors import Evey2ObsError
        from evey2obs.models import ErrorCode

        with patch.object(bilibili_adapter, "_get_cid", return_value=None), \
             patch.object(
                bilibili_adapter, "_run_ytdlp", side_effect=Evey2ObsError(
                    code=ErrorCode.CONTENT_UNAVAILABLE,
                    message="HTTP Error 403: Forbidden",
                )
            ):
            with pytest.raises(Evey2ObsError) as exc:
                await bilibili_adapter.extract_media(
                    _make_rs(),
                )
            assert exc.value.code == ErrorCode.CONTENT_UNAVAILABLE


def _make_rs() -> ResolvedSource:  # noqa: F821
    from evey2obs.models import ResolvedSource
    return ResolvedSource(
        source_type=SourceType.BILIBILI,
        content_type=ContentType.VIDEO,
        canonical_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_id="BV1xx411c7mD",
    )
