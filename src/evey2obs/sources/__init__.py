"""Platform source adapters and adapter registry."""

from __future__ import annotations

from evey2obs.errors import Evey2ObsError
from evey2obs.models import ErrorCode, SourceInput
from evey2obs.protocols import SourceAdapter
from evey2obs.sources.base import YtDlpAdapter
from evey2obs.sources.bilibili import BilibiliAdapter
from evey2obs.sources.douyin import DouyinAdapter
from evey2obs.sources.local_file import LocalFileAdapter
from evey2obs.sources.wechat_article import WeChatArticleAdapter
from evey2obs.sources.xiaohongshu import XiaohongshuAdapter
from evey2obs.sources.xiaoyuzhou import XiaoyuzhouAdapter
from evey2obs.sources.youtube import YouTubeAdapter


def _build_registry() -> tuple[SourceAdapter, ...]:
    """Build the default adapter registry."""
    from evey2obs.settings import AppSettings

    settings = AppSettings.from_env()
    return (
        BilibiliAdapter(settings),
        YouTubeAdapter(settings),
        DouyinAdapter(settings),
        XiaohongshuAdapter(settings),
        WeChatArticleAdapter(settings),
        XiaoyuzhouAdapter(settings),
        LocalFileAdapter(),
    )


_registry: tuple[SourceAdapter, ...] | None = None


def get_adapters() -> tuple[SourceAdapter, ...]:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


def find_adapter(source_input: SourceInput) -> SourceAdapter:
    for adapter in get_adapters():
        if adapter.can_handle(source_input):
            return adapter
    raise Evey2ObsError(
        code=ErrorCode.SOURCE_UNSUPPORTED,
        message="No adapter found for the given input",
        detail=f"URLs: {source_input.urls}, Files: {source_input.local_files}",
    )


__all__ = [
    "BilibiliAdapter",
    "DouyinAdapter",
    "LocalFileAdapter",
    "WeChatArticleAdapter",
    "XiaohongshuAdapter",
    "XiaoyuzhouAdapter",
    "YouTubeAdapter",
    "YtDlpAdapter",
    "find_adapter",
    "get_adapters",
]
