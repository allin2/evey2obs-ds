"""Bridge between tkinter's synchronous main loop and asyncio pipeline."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading

from evey2obs.events import ProgressEvent
from evey2obs.pipeline import ProcessingPipeline
from evey2obs.settings import AppSettings

logger = logging.getLogger(__name__)


class AsyncioBridge:
    """Runs ProcessingPipeline in a background asyncio thread.

    All pipeline calls are dispatched via ``asyncio.run_coroutine_threadsafe``.
    Progress events are pushed into a thread-safe queue and polled by tkinter's
    ``.after()`` timer on the main thread.
    """

    def __init__(self, settings: AppSettings) -> None:
        self._pipeline = ProcessingPipeline(settings)
        self._event_queue: queue.Queue[ProgressEvent] = queue.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._running = False

        # Wire progress callback
        self._pipeline.on_progress(self._on_progress)

        # Start background asyncio thread
        self._start()

    # ── Public API (called from tkinter main thread) ──────────────────────

    @property
    def pipeline(self) -> ProcessingPipeline:
        return self._pipeline

    def submit(
        self,
        source_input,
        force_refresh: bool = False,
        template: str | None = None,
    ):
        """Submit tasks; returns task IDs immediately."""

        future = asyncio.run_coroutine_threadsafe(
            self._pipeline.submit(
                source_input, force_refresh=force_refresh, template=template
            ),
            self._loop,  # type: ignore[arg-type]
        )
        return future.result(timeout=10)

    def retry_export(self, recovery_id: str):
        """Retry exporting a draft from pending exports."""
        exporter = self._pipeline._build_exporter()
        future = asyncio.run_coroutine_threadsafe(
            self._pipeline.pending_exports.retry_export(recovery_id, exporter),
            self._loop,  # type: ignore[arg-type]
        )
        return future.result(timeout=30)

    def cancel(self, task_id: str) -> None:
        """Cancel a running task."""
        asyncio.run_coroutine_threadsafe(
            self._pipeline.cancel(task_id), self._loop  # type: ignore[arg-type]
        )

    def get_result(self, task_id: str) -> tuple:
        """Return (ContentDocument|None, ExportResult|None) for a completed task."""
        return self._pipeline.get_result(task_id)

    def get_task(self, task_id: str):
        """Return the Task object for a given ID."""
        return self._pipeline._tasks.get(task_id)

    def poll_events(self) -> list[ProgressEvent]:
        """Drain all pending progress events. Called by tkinter .after() timer."""
        events: list[ProgressEvent] = []
        while True:
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return events

    def shutdown(self) -> None:
        """Cancel all tasks, stop event loop, join thread."""
        self._running = False
        if self._loop:
            # Cancel all active tasks
            for task_id in list(self._pipeline._cancel_tokens.keys()):
                try:
                    asyncio.run_coroutine_threadsafe(
                        self._pipeline.cancel(task_id), self._loop
                    )
                except Exception:
                    pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    # ── Internal ──────────────────────────────────────────────────────────

    def _start(self) -> None:
        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()  # type: ignore[union-attr]

    def _on_progress(self, event: ProgressEvent) -> None:
        """Callback from pipeline — push event into thread-safe queue."""
        try:
            self._event_queue.put_nowait(event)
        except queue.Full:
            pass
