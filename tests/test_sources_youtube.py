"""Tests for YouTubeAdapter — fixture-based, no real network."""

from __future__ import annotations

import json

import pytest

from evey2obs.models import ContentType, SourceInput, SourceType
from evey2obs.protocols import SourceAdapter
from evey2obs.settings import AppSettings
from evey2obs.sources.youtube import YouTubeAdapter


@pytest.fixture
def youtube_adapter() -> YouTubeAdapter:
    return YouTubeAdapter(AppSettings())


class TestProtocolCompliance:
    def test_implements_source_adapter_protocol(
        self, youtube_adapter: YouTubeAdapter
    ) -> None:
        assert isinstance(youtube_adapter, SourceAdapter)


class TestCanHandle:
    def test_youtube_url_true(self, youtube_adapter: YouTubeAdapter) -> None:
        si = SourceInput.from_urls(["https://www.youtube.com/watch?v=abc12345678"])
        assert youtube_adapter.can_handle(si)

    def test_youtu_be_true(self, youtube_adapter: YouTubeAdapter) -> None:
        si = SourceInput.from_urls(["https://youtu.be/abc12345678"])
        assert youtube_adapter.can_handle(si)

    def test_bilibili_url_false(self, youtube_adapter: YouTubeAdapter) -> None:
        si = SourceInput.from_urls(["https://www.bilibili.com/video/BV123"])
        assert not youtube_adapter.can_handle(si)


class TestResolve:
    @pytest.mark.asyncio
    async def test_extracts_video_id(self, youtube_adapter: YouTubeAdapter) -> None:
        from unittest.mock import patch

        with patch.object(youtube_adapter, "_run_ytdlp") as mock_run:
            mock_run.return_value = "https://www.youtube.com/watch?v=abc12345678"
            si = SourceInput.from_urls(["https://youtu.be/abc12345678"])
            result = await youtube_adapter.resolve(si)
            assert result.source_type == SourceType.YOUTUBE
            assert result.source_id == "abc12345678"


class TestExtractMetadata:
    @pytest.mark.asyncio
    async def test_parses_metadata_json(self, youtube_adapter: YouTubeAdapter) -> None:
        from unittest.mock import patch

        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.YOUTUBE,
            content_type=ContentType.VIDEO,
            canonical_url="https://www.youtube.com/watch?v=abc12345678",
            source_id="abc12345678",
        )

        metadata_json = json.dumps({
            "title": "Test Video",
            "uploader": "TestChannel",
            "upload_date": "20260617",
            "duration": 300.0,
            "description": "Description text",
        })

        with patch.object(youtube_adapter, "_run_ytdlp", return_value=metadata_json):
            result = await youtube_adapter.extract_metadata(rs)
            assert result.title == "Test Video"
            assert result.author == "TestChannel"
            assert result.duration_seconds == 300.0
