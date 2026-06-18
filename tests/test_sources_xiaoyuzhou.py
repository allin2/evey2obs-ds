"""Tests for XiaoyuzhouAdapter — fixture-based, no real network."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from evey2obs.models import ContentType, SourceInput, SourceType
from evey2obs.protocols import SourceAdapter
from evey2obs.settings import AppSettings
from evey2obs.sources.xiaoyuzhou import XiaoyuzhouAdapter

MOCK_NEXT_DATA = {
    "props": {
        "pageProps": {
            "episode": {
                "title": "Test Episode",
                "podcast": {"title": "Test Podcast"},
                "shownotes": "Show notes content here",
                "transcript": "Full transcript text with timestamps",
                "duration": 3600,
            },
        },
    },
}

MOCK_NEXT_DATA_NO_TRANSCRIPT = {
    "props": {
        "pageProps": {
            "episode": {
                "title": "Test Episode No Transcript",
                "podcast": {"title": "Test Podcast"},
                "shownotes": "Show notes only",
                "transcript": "",
            },
        },
    },
}


def _make_episode_html(next_data: dict) -> str:
    json_str = json.dumps(next_data, ensure_ascii=False)
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json_str}</script></html>'


@pytest.fixture
def xyz_adapter() -> XiaoyuzhouAdapter:
    return XiaoyuzhouAdapter(AppSettings())


class TestProtocolCompliance:
    def test_implements_protocol(self, xyz_adapter: XiaoyuzhouAdapter) -> None:
        assert isinstance(xyz_adapter, SourceAdapter)


class TestCanHandle:
    def test_xiaoyuzhou_url_true(self, xyz_adapter: XiaoyuzhouAdapter) -> None:
        si = SourceInput.from_urls(["https://www.xiaoyuzhoufm.com/episode/abc123"])
        assert xyz_adapter.can_handle(si)

    def test_non_podcast_false(self, xyz_adapter: XiaoyuzhouAdapter) -> None:
        si = SourceInput.from_urls(["https://example.com/podcast"])
        assert not xyz_adapter.can_handle(si)


class TestSourceId:
    def test_extracts_episode_id(self, xyz_adapter: XiaoyuzhouAdapter) -> None:
        sid = xyz_adapter._extract_source_id("https://www.xiaoyuzhoufm.com/episode/12345abc")
        assert sid == "12345abc"


class TestResolve:
    @pytest.mark.asyncio
    async def test_returns_audio_type(self, xyz_adapter: XiaoyuzhouAdapter) -> None:
        with patch.object(xyz_adapter, "_run_ytdlp", return_value="https://www.xiaoyuzhoufm.com/episode/abc"):
            si = SourceInput.from_urls(["https://www.xiaoyuzhoufm.com/episode/abc"])
            result = await xyz_adapter.resolve(si)
            assert result.source_type == SourceType.XIAOYUZHOU
            assert result.content_type == ContentType.AUDIO


class TestParseNextData:
    def test_parses_transcript(self) -> None:
        data = XiaoyuzhouAdapter._parse_next_data(
            _make_episode_html(MOCK_NEXT_DATA)
        )
        assert data is not None
        assert data["title"] == "Test Episode"
        assert data["transcript"] == "Full transcript text with timestamps"
        assert data["podcast_name"] == "Test Podcast"


class TestExtractText:
    @pytest.mark.asyncio
    async def test_with_transcript(self, xyz_adapter: XiaoyuzhouAdapter) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.XIAOYUZHOU,
            content_type=ContentType.AUDIO,
            canonical_url="https://www.xiaoyuzhoufm.com/episode/abc",
            source_id="abc",
        )
        with patch.object(xyz_adapter, "_scrape_episode_page") as mock_scrape:
            mock_scrape.return_value = {
                "title": "Test",
                "transcript": "Full transcript",
            }
            result = await xyz_adapter.extract_text(rs)
            assert result is not None
            assert result.text == "Full transcript"

    @pytest.mark.asyncio
    async def test_no_transcript_returns_none(self, xyz_adapter: XiaoyuzhouAdapter) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.XIAOYUZHOU,
            content_type=ContentType.AUDIO,
            canonical_url="https://www.xiaoyuzhoufm.com/episode/abc",
            source_id="abc",
        )
        with patch.object(xyz_adapter, "_scrape_episode_page") as mock_scrape:
            mock_scrape.return_value = {
                "title": "Test",
                "transcript": "",
            }
            result = await xyz_adapter.extract_text(rs)
            assert result is None  # Triggers Whisper fallback
