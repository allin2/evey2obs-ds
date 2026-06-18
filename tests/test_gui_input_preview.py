"""Tests for URL extraction and platform identification used by the GUI."""

from evey2obs.inputs import extract_urls, identify_source
from evey2obs.models import SourceType


class TestMultiUrlExtraction:
    def test_multiline_paste(self) -> None:
        text = "https://www.bilibili.com/video/BV123\nhttps://youtube.com/watch?v=abc\nplain text"
        urls = extract_urls(text)
        assert len(urls) == 2

    def test_share_text_with_mixed_platforms(self) -> None:
        text = "快看这个 B站视频 https://b23.tv/xyz 还有这个 YouTube https://youtu.be/abc"
        urls = extract_urls(text)
        assert len(urls) == 2

    def test_dedup_across_multiple_lines(self) -> None:
        text = "https://bilibili.com/video/BV1\nhttps://bilibili.com/video/BV1 again"
        urls = extract_urls(text)
        assert len(urls) == 1

    def test_empty_multiline(self) -> None:
        assert extract_urls("\n\n  \n") == []


class TestMultiPlatformIdentification:
    def test_identify_all_seven_platforms(self) -> None:
        tests = [
            ("https://www.bilibili.com/video/BV123", SourceType.BILIBILI),
            ("https://youtube.com/watch?v=abc", SourceType.YOUTUBE),
            ("https://v.douyin.com/abc/", SourceType.DOUYIN),
            ("https://xhslink.com/abc", SourceType.XIAOHONGSHU),
            ("https://mp.weixin.qq.com/s/abc", SourceType.WECHAT_ARTICLE),
            ("https://www.xiaoyuzhoufm.com/episode/abc", SourceType.XIAOYUZHOU),
        ]
        for url, expected in tests:
            assert identify_source(url) == expected, f"Failed for {url}"

    def test_unknown_platform(self) -> None:
        assert identify_source("https://example.com/video") is None
