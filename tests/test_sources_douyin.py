"""Tests for DouyinAdapter — fixture-based, no real network."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from evey2obs.models import ContentType, SourceInput, SourceType
from evey2obs.protocols import SourceAdapter
from evey2obs.settings import AppSettings
from evey2obs.sources.douyin import DouyinAdapter


@pytest.fixture
def douyin_adapter() -> DouyinAdapter:
    return DouyinAdapter(AppSettings())


class TestProtocolCompliance:
    def test_implements_source_adapter_protocol(
        self, douyin_adapter: DouyinAdapter
    ) -> None:
        assert isinstance(douyin_adapter, SourceAdapter)


class TestCanHandle:
    def test_v_douyin_url_true(self, douyin_adapter: DouyinAdapter) -> None:
        si = SourceInput.from_urls(["https://v.douyin.com/abc123/"])
        assert douyin_adapter.can_handle(si)

    def test_douyin_com_video_true(self, douyin_adapter: DouyinAdapter) -> None:
        si = SourceInput.from_urls(["https://www.douyin.com/video/123456789"])
        assert douyin_adapter.can_handle(si)

    def test_youtube_url_false(self, douyin_adapter: DouyinAdapter) -> None:
        si = SourceInput.from_urls(["https://www.youtube.com/watch?v=abc12345678"])
        assert not douyin_adapter.can_handle(si)

    def test_share_text_with_douyin(self, douyin_adapter: DouyinAdapter) -> None:
        si = SourceInput(raw_text="8.79 复制打开抖音 https://v.douyin.com/abc/ 看看")
        assert douyin_adapter.can_handle(si)


class TestResolve:
    @pytest.mark.asyncio
    async def test_extracts_video_id(self, douyin_adapter: DouyinAdapter) -> None:
        with patch.object(douyin_adapter, "_run_ytdlp") as mock_run:
            mock_run.return_value = "https://www.douyin.com/video/123456789"
            si = SourceInput.from_urls(["https://v.douyin.com/abc/"])
            result = await douyin_adapter.resolve(si)
            assert result.source_type == SourceType.DOUYIN
            assert result.content_type == ContentType.VIDEO
            assert result.source_id == "123456789"


class TestExtractMetadata:
    @pytest.mark.asyncio
    async def test_parses_metadata_json(self, douyin_adapter: DouyinAdapter) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.DOUYIN,
            content_type=ContentType.VIDEO,
            canonical_url="https://www.douyin.com/video/123456789",
            source_id="123456789",
        )
        metadata_json = json.dumps({
            "title": "抖音视频",
            "uploader": "抖音用户",
            "upload_date": "20260617",
            "duration": 30.0,
            "description": "视频描述",
        })
        with patch.object(douyin_adapter, "_run_ytdlp", return_value=metadata_json):
            result = await douyin_adapter.extract_metadata(rs)
            assert result.title == "抖音视频"
            assert result.author == "抖音用户"
            assert result.duration_seconds == 30.0
