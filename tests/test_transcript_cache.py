"""Tests for TranscriptionCache."""

from pathlib import Path

from evey2obs.models import ExtractedText, ExtractionMethod, Segment, SourceType
from evey2obs.processors.transcript_cache import TranscriptionCache


def test_cache_miss(tmp_path: Path):
    cache = TranscriptionCache(tmp_path)
    result = cache.load(SourceType.BILIBILI, "BV123", "small")
    assert result is None


def test_cache_store_and_load(tmp_path: Path):
    cache = TranscriptionCache(tmp_path)
    extracted = ExtractedText(
        text="Hello world from cache test.",
        segments=(
            Segment(start=0.0, end=1.5, text="Hello world"),
            Segment(start=1.5, end=3.0, text="from cache test."),
        ),
        extraction_method=ExtractionMethod.WHISPER,
    )

    stored = cache.store(SourceType.BILIBILI, "BV123", "small", extracted)
    assert stored is True

    loaded = cache.load(SourceType.BILIBILI, "BV123", "small")
    assert loaded is not None
    assert loaded.text == extracted.text
    assert len(loaded.segments) == 2
    assert loaded.segments[0].text == "Hello world"
    assert loaded.extraction_method == ExtractionMethod.CACHE


def test_cache_model_mismatch(tmp_path: Path):
    cache = TranscriptionCache(tmp_path)
    extracted = ExtractedText(
        text="Sample text",
        segments=(),
        extraction_method=ExtractionMethod.WHISPER,
    )
    cache.store(SourceType.YOUTUBE, "vid123", "small", extracted)

    # Different model should miss
    assert cache.load(SourceType.YOUTUBE, "vid123", "medium") is None


def test_cache_local_file(tmp_path: Path):
    cache = TranscriptionCache(tmp_path)
    dummy_media = tmp_path / "audio.mp3"
    dummy_media.write_bytes(b"dummy audio content")

    extracted = ExtractedText(
        text="Local audio transcribed",
        segments=(Segment(start=0.0, end=2.0, text="Local audio transcribed"),),
        extraction_method=ExtractionMethod.WHISPER,
    )

    stored = cache.store(
        SourceType.LOCAL_FILE, "audio.mp3", "small", extracted, file_path=dummy_media
    )
    assert stored is True

    loaded = cache.load(
        SourceType.LOCAL_FILE, "audio.mp3", "small", file_path=dummy_media
    )
    assert loaded is not None
    assert loaded.text == "Local audio transcribed"


def test_cache_clear(tmp_path: Path):
    cache = TranscriptionCache(tmp_path)
    extracted = ExtractedText(
        text="Text", segments=(), extraction_method=ExtractionMethod.WHISPER
    )
    cache.store(SourceType.BILIBILI, "BV1", "small", extracted)
    cache.store(SourceType.BILIBILI, "BV2", "small", extracted)

    assert cache.clear() == 2
    assert cache.load(SourceType.BILIBILI, "BV1", "small") is None
