"""Tests for WeChatArticleAdapter — fixture-based, no real network."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from evey2obs.models import ContentType, SourceInput, SourceType
from evey2obs.protocols import SourceAdapter
from evey2obs.settings import AppSettings
from evey2obs.sources.wechat_article import WeChatArticleAdapter

MOCK_ARTICLE_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta property="og:title" content="Test Article Title">
  <meta property="og:article:author" content="TestAuthor">
</head>
<body>
  <div id="img-content">
    <h1 id="activity-name">Test Article Title</h1>
    <span id="js_name">TestAuthor</span>
    <em id="publish_time">2026-06-15</em>
    <div id="js_content">
      <p>First paragraph with <a href="https://example.com">a link</a>.</p>
      <img data-src="https://mmbiz.qpic.cn/fake1.jpg" alt="photo">
      <ul><li>Item one</li><li>Item two</li></ul>
      <blockquote>A quoted passage</blockquote>
      <p>Second paragraph.</p>
    </div>
  </div>
</body>
</html>"""

MOCK_CAPTCHA_HTML = "<html><body>环境异常 请输入验证码</body></html>"
MOCK_DELETED_HTML = "<html><body>该内容已被发布者删除</body></html>"


@pytest.fixture
def wechat_adapter() -> WeChatArticleAdapter:
    return WeChatArticleAdapter(AppSettings())


class TestProtocolCompliance:
    def test_implements_protocol(self, wechat_adapter: WeChatArticleAdapter) -> None:
        assert isinstance(wechat_adapter, SourceAdapter)


class TestCanHandle:
    def test_wechat_url_true(self, wechat_adapter: WeChatArticleAdapter) -> None:
        si = SourceInput.from_urls(["https://mp.weixin.qq.com/s/abc123"])
        assert wechat_adapter.can_handle(si)

    def test_non_wechat_false(self, wechat_adapter: WeChatArticleAdapter) -> None:
        si = SourceInput.from_urls(["https://example.com/article"])
        assert not wechat_adapter.can_handle(si)


class TestSourceId:
    def test_extracts_from_standard_url(self, wechat_adapter: WeChatArticleAdapter) -> None:
        sid = wechat_adapter._extract_source_id("https://mp.weixin.qq.com/s/abc123_xyz")
        assert sid == "abc123_xyz"


class TestResolve:
    @pytest.mark.asyncio
    async def test_returns_article_type(self, wechat_adapter: WeChatArticleAdapter) -> None:
        si = SourceInput.from_urls(["https://mp.weixin.qq.com/s/abc123"])
        result = await wechat_adapter.resolve(si)
        assert result.source_type == SourceType.WECHAT_ARTICLE
        assert result.content_type == ContentType.ARTICLE


class TestExtractMetadata:
    @pytest.mark.asyncio
    async def test_parses_metadata(self, wechat_adapter: WeChatArticleAdapter) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.WECHAT_ARTICLE,
            content_type=ContentType.ARTICLE,
            canonical_url="https://mp.weixin.qq.com/s/abc123",
            source_id="abc123",
        )
        with patch.object(wechat_adapter, "_fetch_page", return_value=MOCK_ARTICLE_HTML):
            result = await wechat_adapter.extract_metadata(rs)
            assert result.title == "Test Article Title"
            assert result.author == "TestAuthor"


class TestExtractText:
    @pytest.mark.asyncio
    async def test_extracts_markdown_body(self, wechat_adapter: WeChatArticleAdapter) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.WECHAT_ARTICLE,
            content_type=ContentType.ARTICLE,
            canonical_url="https://mp.weixin.qq.com/s/abc123",
            source_id="abc123",
        )
        with patch.object(wechat_adapter, "_fetch_page", return_value=MOCK_ARTICLE_HTML), \
             patch.object(wechat_adapter, "_download_image", return_value=None):
            result = await wechat_adapter.extract_text(rs)
            assert result is not None
            assert "First paragraph" in result.text
            assert "[a link](https://example.com)" in result.text
            assert "- Item one" in result.text
            assert "> A quoted passage" in result.text


class TestBlockedStates:
    @pytest.mark.asyncio
    async def test_captcha_raises(self, wechat_adapter: WeChatArticleAdapter) -> None:
        from evey2obs.errors import Evey2ObsError
        from evey2obs.models import ErrorCode, ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.WECHAT_ARTICLE,
            content_type=ContentType.ARTICLE,
            canonical_url="https://mp.weixin.qq.com/s/abc123",
            source_id="abc123",
        )
        with patch.object(wechat_adapter, "_fetch_page", return_value=MOCK_CAPTCHA_HTML):
            with pytest.raises(Evey2ObsError) as exc:
                await wechat_adapter.extract_text(rs)
            assert exc.value.code == ErrorCode.ARTICLE_CHALLENGE

    @pytest.mark.asyncio
    async def test_deleted_raises(self, wechat_adapter: WeChatArticleAdapter) -> None:
        from evey2obs.errors import Evey2ObsError
        from evey2obs.models import ErrorCode, ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.WECHAT_ARTICLE,
            content_type=ContentType.ARTICLE,
            canonical_url="https://mp.weixin.qq.com/s/abc123",
            source_id="abc123",
        )
        with patch.object(wechat_adapter, "_fetch_page", return_value=MOCK_DELETED_HTML):
            with pytest.raises(Evey2ObsError) as exc:
                await wechat_adapter.extract_text(rs)
            assert exc.value.code == ErrorCode.CONTENT_UNAVAILABLE


class TestExtractMedia:
    @pytest.mark.asyncio
    async def test_always_returns_none(self, wechat_adapter: WeChatArticleAdapter) -> None:
        result = await wechat_adapter.extract_media(None)  # type: ignore[arg-type]
        assert result is None
