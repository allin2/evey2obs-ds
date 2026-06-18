"""Processing pipeline that orchestrates the full content extraction flow.

Connects: SourceAdapter → TranscriptionProcessor → SummarizationProcessor
→ ObsidianExporter → MediaCleaner.

This is the missing FR-020 / FR-016 implementation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from evey2obs.cleaner import MediaCleaner
from evey2obs.errors import Evey2ObsError
from evey2obs.events import CancelToken, ProgressEvent
from evey2obs.exporters.obsidian import ObsidianExporter
from evey2obs.models import (
    ContentDocument,
    ErrorCode,
    ExportResult,
    ExtractionMethod,
    SourceInput,
    Task,
    TaskStatus,
    TemporaryMedia,
)
from evey2obs.processors.media import MediaProcessor
from evey2obs.processors.summarization import SummarizationProcessor
from evey2obs.processors.transcription import TranscriptionProcessor
from evey2obs.protocols import (
    Cleaner,
    Exporter,
    SourceAdapter,
    Summarizer,
    Transcriber,
)
from evey2obs.settings import AppSettings, ObsidianSettings
from evey2obs.sources import find_adapter

logger = logging.getLogger(__name__)

_STAGE_PROGRESS: dict[TaskStatus, float] = {
    TaskStatus.QUEUED: 0.0,
    TaskStatus.RESOLVING: 0.1,
    TaskStatus.EXTRACTING: 0.25,
    TaskStatus.TRANSCRIBING: 0.45,
    TaskStatus.SUMMARIZING: 0.7,
    TaskStatus.EXPORTING: 0.85,
    TaskStatus.CLEANING: 0.95,
    TaskStatus.SUCCEEDED: 1.0,
}


class ProcessingPipeline:
    """Orchestrates the full content extraction and export flow.

    Usage::

        settings = AppSettings.from_env()
        pipeline = ProcessingPipeline(settings)
        tasks = await pipeline.submit(SourceInput.from_urls(["https://..."]))
        results = await pipeline.wait_all(tasks)
    """

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._tasks: dict[str, Task] = {}
        self._cancel_tokens: dict[str, CancelToken] = {}
        self._progress_callbacks: list[callable] = []
        self._results: dict[str, ExportResult] = {}
        self._documents: dict[str, ContentDocument] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def on_progress(self, callback: callable) -> None:
        """Register a callback receiving ``ProgressEvent`` for each task update."""
        self._progress_callbacks.append(callback)

    async def submit(self, source_input: SourceInput) -> list[Task]:
        """Create tasks for each URL and start processing.

        Returns immediately with tasks in QUEUED state.
        Processing continues asynchronously.
        """
        from evey2obs.inputs import extract_urls

        urls = list(source_input.urls)
        if source_input.raw_text:
            urls.extend(extract_urls(source_input.raw_text))
        urls = list(dict.fromkeys(urls))

        # Also handle local files as a single task
        if source_input.local_files:
            urls.append("__local__")

        if not urls:
            return []

        tasks: list[Task] = []
        for i, url in enumerate(urls):
            task_id = f"task-{datetime.now(UTC).timestamp()}-{i}"
            task = Task(id=task_id)
            self._tasks[task_id] = task
            self._cancel_tokens[task_id] = CancelToken()
            tasks.append(task)

            # Start processing in background
            asyncio.create_task(self._process_task(task_id, url, source_input))

        return tasks

    def get_result(self, task_id: str) -> tuple[ContentDocument | None, ExportResult | None]:
        """Return the final document and export result for a completed task."""
        return (self._documents.get(task_id), self._results.get(task_id))

    async def cancel(self, task_id: str) -> None:
        """Cancel a running task."""
        token = self._cancel_tokens.get(task_id)
        if token:
            token.cancel()
        task = self._tasks.get(task_id)
        if task and task.status.is_active:
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now(UTC)
            self._emit(task, "Task cancelled by user")

    async def wait_all(self, tasks: list[Task]) -> list[Task]:
        """Wait for all tasks to reach a terminal state."""
        while True:
            all_done = True
            for t in tasks:
                # Refresh from stored state
                current = self._tasks.get(t.id, t)
                t.status = current.status
                t.progress = current.progress
                t.error_code = current.error_code
                t.error_message = current.error_message
                t.updated_at = current.updated_at
                if current.status.is_active:
                    all_done = False
            if all_done:
                break
            await asyncio.sleep(0.1)
        return tasks

    # ── Internal: task processing ─────────────────────────────────────────

    async def _process_task(
        self, task_id: str, url: str, source_input: SourceInput
    ) -> None:
        task = self._tasks[task_id]
        cancel = self._cancel_tokens[task_id]
        media_items: list[TemporaryMedia] = []

        try:
            # ── Stage 1: Resolve source ──────────────────────────────────
            self._transition(task, TaskStatus.RESOLVING, "Identifying source")
            adapters: SourceAdapter = (
                self._get_local_adapter(source_input)
                if url == "__local__"
                else find_adapter(SourceInput.from_urls([url]))
            )

            source = await adapters.resolve(
                source_input
                if url == "__local__"
                else SourceInput.from_urls([url])
            )

            # ── Stage 2: Extract metadata ─────────────────────────────────
            self._transition(task, TaskStatus.EXTRACTING, "Extracting metadata")
            metadata = await adapters.extract_metadata(source)

            # ── Stage 3: Extract text or media ────────────────────────────
            text = await adapters.extract_text(source)

            if text is None or not text.text.strip():
                # ── Stage 3b: Transcribe ──────────────────────────────────
                self._transition(task, TaskStatus.TRANSCRIBING, "Downloading media")
                media = await adapters.extract_media(source)
                if media:
                    # NEVER clean up local files — only downloaded temp media
                    if url != "__local__":
                        media_items.append(media)

                    transcriber = self._build_transcriber()
                    self._transition(task, TaskStatus.TRANSCRIBING, "Transcribing audio")
                    text = await transcriber.transcribe(media, cancel_token=cancel)
                else:
                    # No text and no media — treat as empty
                    text = self._empty_text()

            # Build content document
            doc = ContentDocument(
                id=source.source_id,
                source_type=source.source_type,
                content_type=source.content_type,
                source_url=url if url != "__local__" else f"file://{source.source_id}",
                canonical_url=source.canonical_url,
                title=metadata.title,
                author=metadata.author,
                published_at=metadata.published_at,
                duration_seconds=metadata.duration_seconds,
                description=metadata.description,
                extraction_method=text.extraction_method,
                text=text.text,
                segments=text.segments,
                images=text.images,
            )

            # ── Stage 4: Summarize ────────────────────────────────────────
            self._transition(task, TaskStatus.SUMMARIZING, "Generating AI summary")
            summarizer = self._build_summarizer()
            summary = await summarizer.summarize(doc)
            doc = ContentDocument(
                id=doc.id,
                source_type=doc.source_type,
                content_type=doc.content_type,
                source_url=doc.source_url,
                canonical_url=doc.canonical_url,
                title=doc.title,
                author=doc.author,
                published_at=doc.published_at,
                duration_seconds=doc.duration_seconds,
                description=doc.description,
                extraction_method=doc.extraction_method,
                text=doc.text,
                segments=doc.segments,
                images=doc.images,
                summary=summary.one_line_summary,
                key_points=summary.key_points,
                action_items=summary.action_items,
                tags=summary.tags,
                warnings=doc.warnings,
            )

            # ── Stage 5: Export ───────────────────────────────────────────
            self._transition(task, TaskStatus.EXPORTING, "Writing to Obsidian")
            exporter = self._build_exporter()
            result = await exporter.export(doc, summary)

            # ── Stage 6: Cleanup ──────────────────────────────────────────
            self._transition(task, TaskStatus.CLEANING, "Cleaning up temp files")
            cleaner = self._build_cleaner()
            await cleaner.cleanup(media_items)

            # ── Complete ──────────────────────────────────────────────────
            task.status = TaskStatus.SUCCEEDED
            task.progress = 1.0
            task.updated_at = datetime.now(UTC)
            self._documents[task_id] = doc
            self._results[task_id] = result
            self._emit(task, f"Export complete: {result.note_path}")

        except Evey2ObsError as exc:
            task.status = TaskStatus.FAILED
            task.error_code = exc.code
            task.error_message = exc.message
            task.updated_at = datetime.now(UTC)
            logger.error("Task %s failed (%s): %s", task.id, exc.code.value, exc.message)
            self._emit(task, f"Failed: {exc}")
            # Clean up DOWNLOADED media on failure (never local files)
            if url != "__local__":
                try:
                    cleaner = self._build_cleaner()
                    await cleaner.cleanup(media_items)
                except Exception:
                    pass

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now(UTC)
            self._emit(task, "Task cancelled")

        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error_code = ErrorCode.CONTENT_UNAVAILABLE
            task.error_message = str(exc)[:500]
            task.updated_at = datetime.now(UTC)
            logger.error("Task %s failed: %s", task.id, str(exc)[:200])
            self._emit(task, f"Unexpected error: {exc}")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _transition(self, task: Task, status: TaskStatus, message: str) -> None:
        task.status = status
        task.progress = _STAGE_PROGRESS.get(status, task.progress)
        task.updated_at = datetime.now(UTC)
        self._emit(task, message)

    def _emit(self, task: Task, message: str) -> None:
        ev = ProgressEvent(
            task_id=task.id,
            status=task.status,
            progress=task.progress,
            message=message,
        )
        for cb in self._progress_callbacks:
            try:
                cb(ev)
            except Exception:
                pass

    def _build_transcriber(self) -> Transcriber:
        media_proc = MediaProcessor(
            temp_dir=Path(self._settings.obsidian.vault_path or "/tmp") / ".evey2obs_temp"
        )
        return TranscriptionProcessor(self._settings, media_processor=media_proc)

    def _build_summarizer(self) -> Summarizer:
        return SummarizationProcessor(self._settings.llm)

    def _build_exporter(self) -> Exporter:
        obsidian = self._settings.obsidian
        return ObsidianExporter(
            ObsidianSettings(
                vault_path=obsidian.vault_path,
                subdir=obsidian.subdir,
                attachment_subdir=obsidian.attachment_subdir,
            )
        )

    def _build_cleaner(self) -> Cleaner:
        return MediaCleaner(retention_hours=self._settings.temp_retention_hours)

    @staticmethod
    def _get_local_adapter(source_input: SourceInput) -> SourceAdapter:
        from evey2obs.sources.local_file import LocalFileAdapter
        return LocalFileAdapter()

    @staticmethod
    def _empty_text() -> ExtractedText:  # noqa: F821
        from evey2obs.models import ExtractedText
        return ExtractedText(text="", extraction_method=ExtractionMethod.CACHE)
