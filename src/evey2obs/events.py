"""Progress events and cancellation support for the task pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from evey2obs.models import TaskStatus


@dataclass(frozen=True)
class ProgressEvent:
    """Immutable progress update emitted by the pipeline.

    Each event represents a point-in-time snapshot of a task's progress
    within a specific stage.  The *message* must use stable, user-facing
    text — raw third-party tool output should never appear here directly.
    """

    task_id: str
    status: TaskStatus
    progress: float  # 0.0 .. 1.0 within the current stage
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class CancelToken:
    """Cooperative cancellation token backed by an ``asyncio.Event``.

    Usage::

        token = CancelToken()
        # ... in a long-running loop:
        token.check()                # raises CancelledError if cancelled
        await token.wait_if_requested()  # async variant
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        """``True`` once :meth:`cancel` has been called."""
        return self._event.is_set()

    def cancel(self) -> None:
        """Request cancellation.  Idempotent — safe to call multiple times."""
        self._event.set()

    def check(self) -> None:
        """Raise :class:`asyncio.CancelledError` if cancellation has been requested.

        Call this from synchronous code paths that want to cooperatively
        respond to cancellation.
        """
        if self._event.is_set():
            raise asyncio.CancelledError("Task cancelled")

    async def wait_if_requested(self) -> None:
        """Await until cancellation is requested, then raise.

        Use this in async code paths that need to wait for the cancel signal
        before aborting.
        """
        await self._event.wait()
        raise asyncio.CancelledError("Task cancelled")
