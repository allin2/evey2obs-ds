"""Tests for domain models (enums and dataclasses)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from evey2obs.models import (
    ContentDocument,
    ContentType,
    ErrorCode,
    ExportResult,
    ExtractedText,
    ExtractionMethod,
    ImageRef,
    ResolvedSource,
    Segment,
    SourceInput,
    SourceMetadata,
    SourceType,
    SummaryResult,
    Task,
    TaskStatus,
    TemporaryMedia,
)

# ── Enum value tests ──────────────────────────────────────────────────────────


class TestSourceType:
    def test_all_seven_platforms_defined(self) -> None:
        assert SourceType.BILIBILI == "bilibili"
        assert SourceType.YOUTUBE == "youtube"
        assert SourceType.DOUYIN == "douyin"
        assert SourceType.XIAOHONGSHU == "xiaohongshu"
        assert SourceType.WECHAT_ARTICLE == "wechat_article"
        assert SourceType.XIAOYUZHOU == "xiaoyuzhou"
        assert SourceType.LOCAL_FILE == "local_file"

    def test_is_string_enum(self) -> None:
        assert isinstance(SourceType.BILIBILI, str)


class TestContentType:
    def test_all_four_types_defined(self) -> None:
        assert ContentType.VIDEO == "video"
        assert ContentType.AUDIO == "audio"
        assert ContentType.ARTICLE == "article"
        assert ContentType.IMAGE_NOTE == "image_note"


class TestExtractionMethod:
    def test_all_six_methods_defined(self) -> None:
        assert ExtractionMethod.YT_DLP == "yt_dlp"
        assert ExtractionMethod.SUBTITLE == "subtitle"
        assert ExtractionMethod.WHISPER == "whisper"
        assert ExtractionMethod.HTML == "html"
        assert ExtractionMethod.OCR == "ocr"
        assert ExtractionMethod.CACHE == "cache"


class TestTaskStatus:
    def test_all_ten_statuses_defined(self) -> None:
        assert TaskStatus.QUEUED == "queued"
        assert TaskStatus.RESOLVING == "resolving"
        assert TaskStatus.EXTRACTING == "extracting"
        assert TaskStatus.TRANSCRIBING == "transcribing"
        assert TaskStatus.SUMMARIZING == "summarizing"
        assert TaskStatus.EXPORTING == "exporting"
        assert TaskStatus.CLEANING == "cleaning"
        assert TaskStatus.SUCCEEDED == "succeeded"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"

    @pytest.mark.parametrize(
        "status,expected",
        [
            (TaskStatus.SUCCEEDED, True),
            (TaskStatus.FAILED, True),
            (TaskStatus.CANCELLED, True),
            (TaskStatus.QUEUED, False),
            (TaskStatus.RESOLVING, False),
            (TaskStatus.EXTRACTING, False),
            (TaskStatus.TRANSCRIBING, False),
            (TaskStatus.SUMMARIZING, False),
            (TaskStatus.EXPORTING, False),
            (TaskStatus.CLEANING, False),
        ],
    )
    def test_is_terminal(self, status: TaskStatus, expected: bool) -> None:
        assert status.is_terminal is expected

    @pytest.mark.parametrize(
        "status,expected",
        [
            (TaskStatus.SUCCEEDED, False),
            (TaskStatus.FAILED, False),
            (TaskStatus.CANCELLED, False),
            (TaskStatus.QUEUED, True),
            (TaskStatus.RESOLVING, True),
            (TaskStatus.EXTRACTING, True),
            (TaskStatus.TRANSCRIBING, True),
            (TaskStatus.SUMMARIZING, True),
            (TaskStatus.EXPORTING, True),
            (TaskStatus.CLEANING, True),
        ],
    )
    def test_is_active(self, status: TaskStatus, expected: bool) -> None:
        assert status.is_active is expected


class TestErrorCode:
    def test_all_eleven_codes_defined(self) -> None:
        assert ErrorCode.INPUT_NO_URL == "INPUT_NO_URL"
        assert ErrorCode.SOURCE_UNSUPPORTED == "SOURCE_UNSUPPORTED"
        assert ErrorCode.SHARE_TOKEN_MISSING == "SHARE_TOKEN_MISSING"
        assert ErrorCode.SHARE_TOKEN_EXPIRED == "SHARE_TOKEN_EXPIRED"
        assert ErrorCode.AUTH_REQUIRED == "AUTH_REQUIRED"
        assert ErrorCode.CONTENT_UNAVAILABLE == "CONTENT_UNAVAILABLE"
        assert ErrorCode.ARTICLE_CHALLENGE == "ARTICLE_CHALLENGE"
        assert ErrorCode.NO_SPEECH == "NO_SPEECH"
        assert ErrorCode.ASR_LOW_CONFIDENCE == "ASR_LOW_CONFIDENCE"
        assert ErrorCode.LLM_FAILED == "LLM_FAILED"
        assert ErrorCode.DISK_FULL == "DISK_FULL"


# ── Value object tests ────────────────────────────────────────────────────────


class TestSegment:
    def test_creation(self) -> None:
        seg = Segment(start=0.0, end=5.2, text="hello")
        assert seg.start == 0.0
        assert seg.end == 5.2
        assert seg.text == "hello"

    def test_frozen(self) -> None:
        seg = Segment(0.0, 1.0, "x")
        with pytest.raises(FrozenInstanceError):
            seg.start = 2.0  # type: ignore[misc]


class TestImageRef:
    def test_creation_with_defaults(self) -> None:
        ref = ImageRef(url="https://example.com/img.jpg")
        assert ref.url == "https://example.com/img.jpg"
        assert ref.local_path is None
        assert ref.caption is None

    def test_creation_full(self) -> None:
        ref = ImageRef(
            url="https://example.com/img.jpg",
            local_path="attachments/img.jpg",
            caption="A photo",
        )
        assert ref.local_path == "attachments/img.jpg"
        assert ref.caption == "A photo"


# ── SourceInput tests ─────────────────────────────────────────────────────────


class TestSourceInput:
    def test_defaults_empty(self) -> None:
        si = SourceInput()
        assert si.raw_text == ""
        assert si.urls == ()
        assert si.local_files == ()

    def test_from_raw(self) -> None:
        si = SourceInput.from_raw("check out https://example.com")
        assert si.raw_text == "check out https://example.com"
        assert si.urls == ()
        assert si.local_files == ()

    def test_from_urls(self) -> None:
        si = SourceInput.from_urls(["https://a.com", "https://b.com"])
        assert si.urls == ("https://a.com", "https://b.com")
        assert si.raw_text == ""

    def test_from_urls_accepts_tuple(self) -> None:
        si = SourceInput.from_urls(("https://a.com",))
        assert si.urls == ("https://a.com",)

    def test_from_local_files(self) -> None:
        si = SourceInput.from_local_files(["audio.mp3", "video.mp4"])
        assert si.local_files == ("audio.mp3", "video.mp4")

    def test_from_local_files_accepts_tuple(self) -> None:
        si = SourceInput.from_local_files(("audio.mp3",))
        assert si.local_files == ("audio.mp3",)

    def test_frozen(self) -> None:
        si = SourceInput(raw_text="hello")
        with pytest.raises(FrozenInstanceError):
            si.raw_text = "world"  # type: ignore[misc]


# ── ResolvedSource tests ──────────────────────────────────────────────────────


class TestResolvedSource:
    def test_creation(self) -> None:
        rs = ResolvedSource(
            source_type=SourceType.BILIBILI,
            content_type=ContentType.VIDEO,
            canonical_url="https://www.bilibili.com/video/BV1xx411c7mD",
            source_id="BV1xx411c7mD",
        )
        assert rs.source_type == SourceType.BILIBILI
        assert rs.content_type == ContentType.VIDEO
        assert rs.source_id == "BV1xx411c7mD"


# ── SourceMetadata tests ──────────────────────────────────────────────────────


class TestSourceMetadata:
    def test_all_none_defaults(self) -> None:
        sm = SourceMetadata()
        assert sm.title is None
        assert sm.author is None
        assert sm.published_at is None
        assert sm.duration_seconds is None
        assert sm.description is None

    def test_partial_population(self) -> None:
        sm = SourceMetadata(title="Test", author="Alice")
        assert sm.title == "Test"
        assert sm.author == "Alice"
        assert sm.duration_seconds is None


# ── ExtractedText tests ───────────────────────────────────────────────────────


class TestExtractedText:
    def test_creation_minimal(self) -> None:
        et = ExtractedText(text="sample text")
        assert et.text == "sample text"
        assert et.segments == ()
        assert et.extraction_method == ExtractionMethod.CACHE

    def test_creation_with_segments(self) -> None:
        seg = Segment(0.0, 1.0, "a")
        et = ExtractedText(
            text="a",
            segments=(seg,),
            extraction_method=ExtractionMethod.WHISPER,
        )
        assert et.segments == (seg,)
        assert et.extraction_method == ExtractionMethod.WHISPER


# ── TemporaryMedia tests ──────────────────────────────────────────────────────


class TestTemporaryMedia:
    def test_creation(self) -> None:
        tm = TemporaryMedia(file_path="/tmp/audio.mp3")
        assert tm.file_path == "/tmp/audio.mp3"
        assert tm.media_type == ""

    def test_with_media_type(self) -> None:
        tm = TemporaryMedia(file_path="/tmp/video.mp4", media_type="video/mp4")
        assert tm.media_type == "video/mp4"


# ── ContentDocument tests ─────────────────────────────────────────────────────


class TestContentDocument:
    def test_minimal_construction(self) -> None:
        doc = ContentDocument(
            id="bv-123",
            source_type=SourceType.BILIBILI,
            content_type=ContentType.VIDEO,
            source_url="https://www.bilibili.com/video/BV123",
            canonical_url="https://www.bilibili.com/video/BV123",
        )
        assert doc.id == "bv-123"
        assert doc.source_type == SourceType.BILIBILI
        assert doc.title is None
        assert doc.text == ""
        assert doc.segments == ()
        assert doc.images == ()
        assert doc.summary == ""
        assert doc.key_points == ()
        assert doc.action_items == ()
        assert doc.tags == ()
        assert doc.warnings == ()

    def test_full_construction(self) -> None:
        seg = Segment(0.0, 1.0, "hello")
        img = ImageRef(url="https://img.example.com/1.jpg")
        doc = ContentDocument(
            id="note-1",
            source_type=SourceType.XIAOHONGSHU,
            content_type=ContentType.IMAGE_NOTE,
            source_url="https://xhslink.com/abc",
            canonical_url="https://www.xiaohongshu.com/explore/abc",
            title="My Note",
            author="user123",
            published_at=datetime(2026, 6, 17, tzinfo=UTC),
            duration_seconds=None,
            description="A test note",
            extraction_method=ExtractionMethod.HTML,
            text="Full body text here",
            segments=(seg,),
            images=(img,),
            summary="One-line summary",
            key_points=("Point 1", "Point 2"),
            action_items=("Do thing",),
            tags=("tag1", "tag2"),
            warnings=("low confidence audio",),
        )
        assert doc.title == "My Note"
        assert doc.author == "user123"
        assert doc.text == "Full body text here"
        assert len(doc.segments) == 1
        assert len(doc.images) == 1
        assert doc.key_points == ("Point 1", "Point 2")
        assert doc.action_items == ("Do thing",)
        assert doc.tags == ("tag1", "tag2")
        assert doc.warnings == ("low confidence audio",)

    def test_frozen(self) -> None:
        doc = ContentDocument(
            id="x",
            source_type=SourceType.BILIBILI,
            content_type=ContentType.VIDEO,
            source_url="https://a.com",
            canonical_url="https://a.com",
        )
        with pytest.raises(FrozenInstanceError):
            doc.title = "new"  # type: ignore[misc]


# ── SummaryResult tests ───────────────────────────────────────────────────────


class TestSummaryResult:
    def test_all_defaults_empty(self) -> None:
        sr = SummaryResult()
        assert sr.one_line_summary == ""
        assert sr.key_points == ()
        assert sr.detailed_notes == ""
        assert sr.action_items == ()
        assert sr.quotes == ()
        assert sr.tags == ()
        assert sr.model_metadata == ()

    def test_model_metadata(self) -> None:
        sr = SummaryResult(
            one_line_summary="summary",
            model_metadata=(("model", "deepseek-v4-pro"), ("provider", "custom")),
        )
        assert sr.model_metadata == (("model", "deepseek-v4-pro"), ("provider", "custom"))

    def test_frozen(self) -> None:
        sr = SummaryResult(one_line_summary="x")
        with pytest.raises(FrozenInstanceError):
            sr.one_line_summary = "y"  # type: ignore[misc]


# ── Task tests ────────────────────────────────────────────────────────────────


class TestTask:
    def test_defaults(self) -> None:
        t = Task(id="task-1")
        assert t.id == "task-1"
        assert t.status == TaskStatus.QUEUED
        assert t.progress == 0.0
        assert t.error_code is None
        assert t.error_message is None
        assert isinstance(t.created_at, datetime)
        assert isinstance(t.updated_at, datetime)

    def test_is_mutable(self) -> None:
        """Task is intentionally NOT frozen — the pipeline mutates it."""
        t = Task(id="task-2")
        t.status = TaskStatus.RESOLVING
        t.progress = 0.5
        t.error_code = ErrorCode.LLM_FAILED
        t.error_message = "timeout"
        assert t.status == TaskStatus.RESOLVING
        assert t.progress == 0.5
        assert t.error_code == ErrorCode.LLM_FAILED

    def test_created_at_is_set_on_init(self) -> None:
        before = datetime.now(UTC)
        t = Task(id="t")
        after = datetime.now(UTC)
        assert before <= t.created_at <= after


# ── ExportResult tests ────────────────────────────────────────────────────────


class TestExportResult:
    def test_creation(self) -> None:
        er = ExportResult(
            note_path="vault/notes/My Note.md",
            attachment_paths=("vault/attachments/img1.jpg",),
            manifest_path="vault/notes/My Note.json",
        )
        assert er.note_path == "vault/notes/My Note.md"
        assert er.attachment_paths == ("vault/attachments/img1.jpg",)
        assert er.manifest_path == "vault/notes/My Note.json"

    def test_manifest_optional(self) -> None:
        er = ExportResult(note_path="vault/notes/Note.md")
        assert er.manifest_path is None
        assert er.attachment_paths == ()
