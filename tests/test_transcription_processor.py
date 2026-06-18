"""Tests for TranscriptionProcessor — Whisper integration and protocol compliance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from evey2obs.errors import Evey2ObsError
from evey2obs.models import ErrorCode, TemporaryMedia
from evey2obs.processors.transcription import TranscriptionProcessor
from evey2obs.protocols import Transcriber
from evey2obs.settings import AppSettings


class TestProtocolCompliance:
    def test_implements_transcriber_protocol(self) -> None:
        proc = TranscriptionProcessor(settings=AppSettings())
        assert isinstance(proc, Transcriber)

    def test_cancel_is_callable(self) -> None:
        proc = TranscriptionProcessor(settings=AppSettings())
        proc.cancel()  # should not raise


class TestTranscribeErrors:
    async def test_no_text_raises_no_speech(self, tmp_path: Path) -> None:
        """When whisper returns empty text, NO_SPEECH error is raised."""
        proc = TranscriptionProcessor(settings=AppSettings())

        # Create a minimal WAV
        import wave
        wav = tmp_path / "silent.wav"
        with wave.open(str(wav), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)

        media = TemporaryMedia(file_path=str(wav), media_type="audio/wav")

        # Mock whisper to return empty
        with patch.object(TranscriptionProcessor, "_load_model", return_value=None), \
             patch.object(TranscriptionProcessor, "_transcribe_file", return_value=[]):
            with pytest.raises(Evey2ObsError) as exc:
                await proc.transcribe(media)
            assert exc.value.code == ErrorCode.NO_SPEECH


class TestCache:
    def test_cache_key_is_stable(self, test_wav: Path) -> None:
        key1 = TranscriptionProcessor._cache_key(test_wav)
        key2 = TranscriptionProcessor._cache_key(test_wav)
        assert key1 == key2
        assert len(key1) == 64  # SHA-256 hex digest

    def test_cache_path_creates_dir(self, tmp_path: Path) -> None:
        import wave
        wav = tmp_path / "test.wav"
        with wave.open(str(wav), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)

        cache_path = TranscriptionProcessor._cache_path(wav)
        assert cache_path.parent.is_dir()

    def test_read_cache_missing_returns_none(self, tmp_path: Path) -> None:
        import wave
        wav = tmp_path / "test.wav"
        with wave.open(str(wav), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)

        proc = TranscriptionProcessor(settings=AppSettings())
        result = proc._read_cache(wav)
        assert result is None

    def test_write_and_read_cache_roundtrip(self, tmp_path: Path, sample_segments: list) -> None:
        import wave
        wav = tmp_path / "test.wav"
        with wave.open(str(wav), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)

        proc = TranscriptionProcessor(settings=AppSettings())
        proc._write_cache(wav, sample_segments)
        result = proc._read_cache(wav)
        assert result is not None
        assert len(result) == len(sample_segments)
        assert result[0].text == sample_segments[0].text
