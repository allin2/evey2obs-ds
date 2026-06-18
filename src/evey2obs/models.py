"""Domain models for evey2obs.

All enums and dataclasses that form the shared language across platform
adapters, processors, exporters, and the GUI/CLI presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

# ── Enums ──────────────────────────────────────────────────────────────────────


class SourceType(StrEnum):
    """Platform source identifier."""

    BILIBILI = "bilibili"
    YOUTUBE = "youtube"
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    WECHAT_ARTICLE = "wechat_article"
    XIAOYUZHOU = "xiaoyuzhou"
    LOCAL_FILE = "local_file"


class ContentType(StrEnum):
    """Type of content being processed."""

    VIDEO = "video"
    AUDIO = "audio"
    ARTICLE = "article"
    IMAGE_NOTE = "image_note"


class ExtractionMethod(StrEnum):
    """How the text content was obtained."""

    YT_DLP = "yt_dlp"
    SUBTITLE = "subtitle"
    WHISPER = "whisper"
    HTML = "html"
    OCR = "ocr"
    CACHE = "cache"


class TaskStatus(StrEnum):
    """Stable task stage identifiers as specified in PRD section 10.3."""

    QUEUED = "queued"
    RESOLVING = "resolving"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    SUMMARIZING = "summarizing"
    EXPORTING = "exporting"
    CLEANING = "cleaning"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """True when the task will not transition further."""
        return self in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED)

    @property
    def is_active(self) -> bool:
        """True when the task is still in progress."""
        return not self.is_terminal


class ErrorCode(StrEnum):
    """Stable error codes from PRD section 14."""

    INPUT_NO_URL = "INPUT_NO_URL"
    SOURCE_UNSUPPORTED = "SOURCE_UNSUPPORTED"
    SHARE_TOKEN_MISSING = "SHARE_TOKEN_MISSING"
    SHARE_TOKEN_EXPIRED = "SHARE_TOKEN_EXPIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    CONTENT_UNAVAILABLE = "CONTENT_UNAVAILABLE"
    ARTICLE_CHALLENGE = "ARTICLE_CHALLENGE"
    NO_SPEECH = "NO_SPEECH"
    ASR_LOW_CONFIDENCE = "ASR_LOW_CONFIDENCE"
    LLM_FAILED = "LLM_FAILED"
    DISK_FULL = "DISK_FULL"


# ── Value objects (frozen) ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Segment:
    """A timestamped segment of transcribed text."""

    start: float
    end: float
    text: str


@dataclass(frozen=True)
class ImageRef:
    """Reference to an image, either remote or local."""

    url: str
    local_path: str | None = None
    caption: str | None = None


# ── Pipeline data contracts ───────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceInput:
    """User input before platform identification.

    At least one of *urls*, *raw_text*, or *local_files* should be non-empty.
    """

    raw_text: str = ""
    urls: tuple[str, ...] = ()
    local_files: tuple[str, ...] = ()

    @classmethod
    def from_raw(cls, raw_text: str) -> SourceInput:
        """Create from raw share text (may contain URLs embedded in prose)."""
        return cls(raw_text=raw_text)

    @classmethod
    def from_urls(cls, urls: tuple[str, ...] | list[str]) -> SourceInput:
        """Create from one or more explicit URLs."""
        return cls(urls=tuple(urls))

    @classmethod
    def from_local_files(cls, paths: tuple[str, ...] | list[str]) -> SourceInput:
        """Create from local file paths."""
        return cls(local_files=tuple(paths))


@dataclass(frozen=True)
class ResolvedSource:
    """Output of platform identification and short-link resolution."""

    source_type: SourceType
    content_type: ContentType
    canonical_url: str
    source_id: str


@dataclass(frozen=True)
class SourceMetadata:
    """Metadata extracted by a platform adapter before full content extraction."""

    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    duration_seconds: float | None = None
    description: str | None = None


@dataclass(frozen=True)
class ExtractedText:
    """Text obtained from subtitles, HTML parsing, or transcription."""

    text: str
    segments: tuple[Segment, ...] = ()
    images: tuple[ImageRef, ...] = ()
    extraction_method: ExtractionMethod = ExtractionMethod.CACHE  # must be overridden by callers


@dataclass(frozen=True)
class TemporaryMedia:
    """Downloaded audio/video file to be consumed by a transcriber and later cleaned up."""

    file_path: str
    media_type: str = ""


# ── Unified content document ──────────────────────────────────────────────────


@dataclass(frozen=True)
class ContentDocument:
    """Normalised document matching PRD section 12.1 JSON structure.

    This is the single interchange format between adapters, processors, and exporters.
    """

    id: str
    source_type: SourceType
    content_type: ContentType
    source_url: str
    canonical_url: str
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    duration_seconds: float | None = None
    description: str | None = None
    extraction_method: ExtractionMethod = ExtractionMethod.CACHE
    text: str = ""
    segments: tuple[Segment, ...] = ()
    images: tuple[ImageRef, ...] = ()
    summary: str = ""
    key_points: tuple[str, ...] = ()
    action_items: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


# ── AI summarizer output ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class SummaryResult:
    """Structured output from the AI summarization step."""

    one_line_summary: str = ""
    key_points: tuple[str, ...] = ()
    detailed_notes: str = ""
    action_items: tuple[str, ...] = ()
    quotes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    model_metadata: tuple[tuple[str, str], ...] = ()


# ── Mutable task tracker ──────────────────────────────────────────────────────


@dataclass
class Task:
    """Mutable task tracker updated by the pipeline during processing.

    Only the pipeline owner (TaskQueue / ProcessingPipeline) should mutate
    *status* and *progress*.  Readers observe the task for progress display.
    """

    id: str
    status: TaskStatus = TaskStatus.QUEUED
    progress: float = 0.0
    error_code: ErrorCode | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ── Exporter output ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExportResult:
    """Result of a successful export to Obsidian or another target."""

    note_path: str
    attachment_paths: tuple[str, ...] = ()
    manifest_path: str | None = None
