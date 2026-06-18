"""Tests for URL extraction and source identification."""

from __future__ import annotations

from evey2obs.inputs import extract_urls, identify_source
from evey2obs.models import SourceType


class TestExtractUrls:
    def test_empty_string(self) -> None:
        assert extract_urls("") == []

    def test_single_url(self) -> None:
        urls = extract_urls("https://www.bilibili.com/video/BV123")
        assert urls == ["https://www.bilibili.com/video/BV123"]

    def test_multiple_urls(self) -> None:
        urls = extract_urls(
            "https://bilibili.com/video/BV1 https://youtube.com/watch?v=abc"
        )
        assert len(urls) == 2

    def test_from_share_text(self) -> None:
        text = "快看这个视频 https://b23.tv/xyz 太有趣了！"
        urls = extract_urls(text)
        assert "https://b23.tv/xyz" in urls

    def test_from_markdown_link(self) -> None:
        text = "[点击这里](https://www.bilibili.com/video/BV456)"
        urls = extract_urls(text)
        assert "https://www.bilibili.com/video/BV456" in urls

    def test_deduplicates(self) -> None:
        text = "https://bilibili.com/video/BV1 and https://bilibili.com/video/BV1 again"
        urls = extract_urls(text)
        assert len(urls) == 1
        assert urls == ["https://bilibili.com/video/BV1"]

    def test_whitespace_only(self) -> None:
        assert extract_urls("   ") == []

    def test_no_urls(self) -> None:
        assert extract_urls("Hello, this is just plain text") == []


class TestIdentifySource:
    def test_bilibili_full_url(self) -> None:
        assert identify_source("https://www.bilibili.com/video/BV123") == SourceType.BILIBILI

    def test_bilibili_short_link(self) -> None:
        assert identify_source("https://b23.tv/xyz") == SourceType.BILIBILI

    def test_youtube_full_url(self) -> None:
        assert identify_source("https://www.youtube.com/watch?v=abc12345678") == SourceType.YOUTUBE

    def test_youtube_short_link(self) -> None:
        assert identify_source("https://youtu.be/abc12345678") == SourceType.YOUTUBE

    def test_youtube_mobile(self) -> None:
        assert identify_source("https://m.youtube.com/watch?v=abc") == SourceType.YOUTUBE

    def test_unsupported_domain(self) -> None:
        assert identify_source("https://example.com/video") is None

    def test_empty_string(self) -> None:
        assert identify_source("") is None

    def test_no_protocol_still_matches(self) -> None:
        assert identify_source("bilibili.com/video/BV123") == SourceType.BILIBILI
