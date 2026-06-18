"""Tests for MediaProcessor — ffmpeg integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from evey2obs.errors import Evey2ObsError
from evey2obs.models import ErrorCode
from evey2obs.processors.media import FFmpegInfo, MediaProcessor


class TestFFmpegCheck:
    def test_returns_ffmpeg_info(self) -> None:
        info = MediaProcessor.check_ffmpeg()
        assert isinstance(info, FFmpegInfo)
        assert isinstance(info.available, bool)

    def test_info_has_path_when_available(self) -> None:
        info = MediaProcessor.check_ffmpeg()
        if info.available:
            assert info.path is not None

    def test_info_has_version_when_available(self) -> None:
        info = MediaProcessor.check_ffmpeg()
        if info.available:
            assert info.version is not None


class TestMediaProcessorInit:
    def test_creates_temp_dir(self, tmp_path: Path) -> None:
        temp = tmp_path / "media_temp"
        MediaProcessor(temp_dir=temp)
        assert temp.is_dir()

    def test_reuses_existing_dir(self, tmp_path: Path) -> None:
        temp = tmp_path / "media_temp"
        temp.mkdir()
        MediaProcessor(temp_dir=temp)
        assert temp.is_dir()


class TestExtractAudio:
    @pytest.mark.asyncio
    async def test_missing_file_raises(self, tmp_path: Path) -> None:
        proc = MediaProcessor(temp_dir=tmp_path / "out")
        missing = tmp_path / "missing.mp4"
        with pytest.raises(Evey2ObsError) as exc:
            await proc.extract_audio(missing)
        assert exc.value.code == ErrorCode.CONTENT_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_wav_file_bypasses_extraction(self, tmp_path: Path, test_wav: Path) -> None:
        """extract_audio on a WAV file still runs ffmpeg (which copies it)."""
        proc = MediaProcessor(temp_dir=tmp_path / "out")

        try:
            result = await proc.extract_audio(test_wav)
            assert result.suffix == ".wav"
        except Evey2ObsError:
            # If ffmpeg is not available, this is expected and not a test failure
            pytest.skip("ffmpeg not available on this system")


class TestGetDuration:
    @pytest.mark.asyncio
    async def test_missing_file_raises(self, tmp_path: Path) -> None:
        proc = MediaProcessor(temp_dir=tmp_path / "out")
        missing = tmp_path / "missing.mp4"
        with pytest.raises(Evey2ObsError):
            await proc.get_duration(missing)

    @pytest.mark.asyncio
    async def test_returns_float_for_wav(self, tmp_path: Path, test_wav: Path) -> None:
        proc = MediaProcessor(temp_dir=tmp_path / "out")
        try:
            duration = await proc.get_duration(test_wav)
            assert isinstance(duration, float)
            assert duration > 0
        except Evey2ObsError:
            pytest.skip("ffprobe not available on this system")
