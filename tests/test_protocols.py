"""Tests for protocol structural subtyping checks."""

from __future__ import annotations

from evey2obs.models import (
    ContentDocument,
    ContentType,
    ExportResult,
    ExtractedText,
    ResolvedSource,
    SourceInput,
    SourceMetadata,
    SourceType,
    SummaryResult,
    TemporaryMedia,
)
from evey2obs.protocols import Cleaner, Exporter, SourceAdapter, Summarizer, Transcriber

# ── Conforming stubs ──────────────────────────────────────────────────────────


class _StubSourceAdapter:
    def can_handle(self, source_input: SourceInput) -> bool:
        return False

    async def resolve(self, source_input: SourceInput) -> ResolvedSource:
        return ResolvedSource(
            source_type=SourceType.BILIBILI,
            content_type=ContentType.VIDEO,
            canonical_url="https://example.com",
            source_id="x",
        )

    async def extract_metadata(self, source: ResolvedSource) -> SourceMetadata:
        return SourceMetadata()

    async def extract_text(self, source: ResolvedSource) -> ExtractedText | None:
        return None

    async def extract_media(self, source: ResolvedSource) -> TemporaryMedia | None:
        return None


class _StubTranscriber:
    async def transcribe(self, media: TemporaryMedia) -> ExtractedText:
        return ExtractedText(text="transcribed")

    def cancel(self) -> None:
        pass


class _StubSummarizer:
    async def summarize(self, document: ContentDocument) -> SummaryResult:
        return SummaryResult()

    def cancel(self) -> None:
        pass


class _StubExporter:
    async def export(
        self, document: ContentDocument, summary: SummaryResult
    ) -> ExportResult:
        return ExportResult(note_path="note.md")


class _StubCleaner:
    async def cleanup(self, media_items: list[TemporaryMedia]) -> None:
        pass


# ── Non-conforming stubs (missing methods) ────────────────────────────────────


class _MissingExtractMedia:
    def can_handle(self, source_input: SourceInput) -> bool:
        return False

    async def resolve(self, source_input: SourceInput) -> ResolvedSource:
        ...  # type: ignore[empty-body]

    async def extract_metadata(self, source: ResolvedSource) -> SourceMetadata:
        ...  # type: ignore[empty-body]

    async def extract_text(self, source: ResolvedSource) -> ExtractedText | None:
        return None


class _MissingCancel:
    async def transcribe(self, media: TemporaryMedia) -> ExtractedText:
        return ExtractedText(text="x")


class _MissingSummarize:
    def cancel(self) -> None:
        pass


class _MissingExport:
    pass


class _MissingCleanup:
    pass


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestSourceAdapterProtocol:
    def test_conforming_instance_passes_isinstance(self) -> None:
        obj = _StubSourceAdapter()
        assert isinstance(obj, SourceAdapter)

    def test_missing_method_fails_isinstance(self) -> None:
        obj = _MissingExtractMedia()
        assert not isinstance(obj, SourceAdapter)

    def test_can_handle_is_sync(self) -> None:
        """can_handle is a regular method, not async."""
        import inspect

        sig = inspect.signature(_StubSourceAdapter.can_handle)
        params = list(sig.parameters)
        # self + source_input
        assert len(params) == 2


class TestTranscriberProtocol:
    def test_conforming_instance_passes_isinstance(self) -> None:
        obj = _StubTranscriber()
        assert isinstance(obj, Transcriber)

    def test_missing_cancel_fails_isinstance(self) -> None:
        obj = _MissingCancel()
        assert not isinstance(obj, Transcriber)


class TestSummarizerProtocol:
    def test_conforming_instance_passes_isinstance(self) -> None:
        obj = _StubSummarizer()
        assert isinstance(obj, Summarizer)

    def test_missing_summarize_fails_isinstance(self) -> None:
        obj = _MissingSummarize()
        assert not isinstance(obj, Summarizer)


class TestExporterProtocol:
    def test_conforming_instance_passes_isinstance(self) -> None:
        obj = _StubExporter()
        assert isinstance(obj, Exporter)

    def test_missing_export_fails_isinstance(self) -> None:
        obj = _MissingExport()
        assert not isinstance(obj, Exporter)


class TestCleanerProtocol:
    def test_conforming_instance_passes_isinstance(self) -> None:
        obj = _StubCleaner()
        assert isinstance(obj, Cleaner)

    def test_missing_cleanup_fails_isinstance(self) -> None:
        obj = _MissingCleanup()
        assert not isinstance(obj, Cleaner)
