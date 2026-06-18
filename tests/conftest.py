"""Shared test fixtures for evey2obs."""

from __future__ import annotations

import wave
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evey2obs.models import (
    ContentDocument,
    ContentType,
    ExtractionMethod,
    ImageRef,
    Segment,
    SourceType,
    SummaryResult,
    TemporaryMedia,
)


@pytest.fixture
def sample_document() -> ContentDocument:
    """A realistic ContentDocument fixture for export tests."""
    return ContentDocument(
        id="test-001",
        source_type=SourceType.BILIBILI,
        content_type=ContentType.VIDEO,
        source_url="https://www.bilibili.com/video/BV123",
        canonical_url="https://www.bilibili.com/video/BV123",
        title="测试视频标题",
        author="测试作者",
        published_at=datetime(2026, 6, 17, tzinfo=UTC),
        extraction_method=ExtractionMethod.SUBTITLE,
        text="这是视频的完整文本内容。\n包含第二行。",
        tags=("测试", "视频"),
        images=(ImageRef(url="https://example.com/img.jpg"),),
    )


@pytest.fixture
def sample_summary() -> SummaryResult:
    """A realistic SummaryResult fixture for export tests."""
    return SummaryResult(
        one_line_summary="这是一句话总结。",
        key_points=("要点一：核心发现", "要点二：次要发现"),
        detailed_notes="详细的笔记内容，支持多段落。",
        action_items=("行动项一：需要跟进的事项",),
        quotes=("这是一段关键引用。",),
        tags=("AI", "视频笔记"),
    )


@pytest.fixture
def long_document() -> ContentDocument:
    """A ContentDocument with long text for chunking tests."""
    return ContentDocument(
        id="test-long",
        source_type=SourceType.YOUTUBE,
        content_type=ContentType.VIDEO,
        source_url="https://youtube.com/watch?v=abc",
        canonical_url="https://youtube.com/watch?v=abc",
        title="Long Video",
        author="Author",
        text="第一段内容。" * 500,  # ~2500 chars × 500 ≈ very long
        tags=("长文本",),
    )


@pytest.fixture
def test_wav(tmp_path: Path) -> Path:
    """Generate a minimal valid WAV file (1 second of silence, 16kHz mono)."""
    wav_path = tmp_path / "test.wav"
    sample_rate = 16000
    duration = 1  # second
    n_samples = sample_rate * duration

    with wave.open(str(wav_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)

    return wav_path


@pytest.fixture
def test_media(test_wav: Path) -> TemporaryMedia:
    """A TemporaryMedia fixture pointing to a real WAV file."""
    return TemporaryMedia(file_path=str(test_wav), media_type="audio/wav")


@pytest.fixture
def sample_segments() -> list[Segment]:
    """Realistic whisper-like segments for testing."""
    return [
        Segment(start=0.0, end=1.5, text="这是第一段测试文本。"),
        Segment(start=1.5, end=3.0, text="这是第二段测试文本。"),
        Segment(start=3.0, end=4.5, text="这是第三段测试文本。"),
    ]
