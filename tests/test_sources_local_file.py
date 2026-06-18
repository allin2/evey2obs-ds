"""Tests for LocalFileAdapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from evey2obs.models import ContentType, SourceInput, SourceType, TemporaryMedia
from evey2obs.protocols import SourceAdapter
from evey2obs.sources.local_file import LocalFileAdapter


class TestProtocolCompliance:
    def test_implements_source_adapter_protocol(self) -> None:
        adapter = LocalFileAdapter()
        assert isinstance(adapter, SourceAdapter)


class TestCanHandle:
    def test_local_files_true(self, tmp_path: Path) -> None:
        f = tmp_path / "audio.mp3"
        f.write_text("dummy")
        si = SourceInput.from_local_files([str(f)])
        assert LocalFileAdapter().can_handle(si)

    def test_no_local_files_false(self) -> None:
        si = SourceInput(raw_text="https://youtube.com")
        assert not LocalFileAdapter().can_handle(si)

    def test_empty_local_files_false(self) -> None:
        si = SourceInput(local_files=())
        assert not LocalFileAdapter().can_handle(si)


class TestResolve:
    @pytest.mark.asyncio
    async def test_video_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.mp4"
        f.write_text("dummy")
        result = await LocalFileAdapter().resolve(SourceInput.from_local_files([str(f)]))
        assert result.source_type == SourceType.LOCAL_FILE
        assert result.content_type == ContentType.VIDEO

    @pytest.mark.asyncio
    async def test_audio_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.mp3"
        f.write_text("dummy")
        result = await LocalFileAdapter().resolve(SourceInput.from_local_files([str(f)]))
        assert result.content_type == ContentType.AUDIO


class TestExtractText:
    @pytest.mark.asyncio
    async def test_always_returns_none(self) -> None:
        result = await LocalFileAdapter().extract_text(None)  # type: ignore[arg-type]
        assert result is None


class TestExtractMedia:
    @pytest.mark.asyncio
    async def test_returns_temporary_media(self, tmp_path: Path) -> None:
        f = tmp_path / "audio.mp3"
        f.write_text("dummy")
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.LOCAL_FILE,
            content_type=ContentType.AUDIO,
            canonical_url=f"file://{f}",
            source_id=str(f),
        )
        result = await LocalFileAdapter().extract_media(rs)
        assert isinstance(result, TemporaryMedia)
        assert result.file_path == str(f.resolve())

    @pytest.mark.asyncio
    async def test_missing_file_returns_none(self) -> None:
        from evey2obs.models import ResolvedSource

        rs = ResolvedSource(
            source_type=SourceType.LOCAL_FILE,
            content_type=ContentType.AUDIO,
            canonical_url="file:///nonexistent.mp3",
            source_id="/nonexistent.mp3",
        )
        result = await LocalFileAdapter().extract_media(rs)
        assert result is None
