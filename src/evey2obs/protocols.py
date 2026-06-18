"""Protocol definitions for evey2obs.

Each protocol is ``@runtime_checkable`` so that ``isinstance(obj, Proto)``
works for structural subtyping checks at runtime.  Implementations do not
need to subclass these protocols explicitly — they only need to provide
matching method signatures.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from evey2obs.models import (
    ContentDocument,
    ExportResult,
    ExtractedText,
    ResolvedSource,
    SourceInput,
    SourceMetadata,
    SummaryResult,
    TemporaryMedia,
)


@runtime_checkable
class SourceAdapter(Protocol):
    """Protocol for a single platform's content extraction adapter.

    Every platform (B站, YouTube, 抖音, etc.) implements this interface.
    Platform-specific details such as authentication, short-link resolution,
    and error mapping are the adapter's responsibility.
    """

    def can_handle(self, source_input: SourceInput) -> bool:
        """Return ``True`` if this adapter can process the given input.

        This is a synchronous check (typically URL pattern matching) that
        does not perform network I/O.
        """
        ...

    async def resolve(self, source_input: SourceInput) -> ResolvedSource:
        """Identify the platform, resolve short-links, and determine content type."""
        ...

    async def extract_metadata(self, source: ResolvedSource) -> SourceMetadata:
        """Fetch title, author, duration, description, and other metadata."""
        ...

    async def extract_text(self, source: ResolvedSource) -> ExtractedText | None:
        """Extract subtitles or article body text directly.

        Returns ``None`` when text is not directly available and the
        pipeline should fall back to media download + transcription.
        """
        ...

    async def extract_media(self, source: ResolvedSource) -> TemporaryMedia | None:
        """Download audio or minimal media for offline transcription.

        Returns ``None`` when media extraction is not needed or not possible.
        """
        ...


@runtime_checkable
class Transcriber(Protocol):
    """Protocol for speech-to-text transcription (Whisper or equivalent)."""

    async def transcribe(self, media: TemporaryMedia) -> ExtractedText:
        """Transcribe the given audio/video media into timestamped text."""
        ...

    def cancel(self) -> None:
        """Cancel any in-progress transcription."""
        ...


@runtime_checkable
class Summarizer(Protocol):
    """Protocol for AI-powered content summarization."""

    async def summarize(self, document: ContentDocument) -> SummaryResult:
        """Generate structured summary from a content document."""
        ...

    def cancel(self) -> None:
        """Cancel any in-progress summarization request."""
        ...


@runtime_checkable
class Exporter(Protocol):
    """Protocol for exporting notes and attachments to a target (e.g. Obsidian)."""

    async def export(
        self, document: ContentDocument, summary: SummaryResult
    ) -> ExportResult:
        """Write the note and attachments, returning paths to the written files."""
        ...


@runtime_checkable
class Cleaner(Protocol):
    """Protocol for cleaning up temporary media after successful export."""

    async def cleanup(self, media_items: list[TemporaryMedia]) -> None:
        """Delete temporary audio, video, and segment files.

        Called only after the exporter has confirmed that the note and all
        attachments are safely written to disk.
        """
        ...
