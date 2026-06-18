"""Tests for progress events and cancellation token."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from evey2obs.events import CancelToken, ProgressEvent
from evey2obs.models import TaskStatus


class TestProgressEvent:
    def test_creation(self) -> None:
        ev = ProgressEvent(
            task_id="task-1",
            status=TaskStatus.TRANSCRIBING,
            progress=0.5,
            message="Transcribing segment 3/8",
        )
        assert ev.task_id == "task-1"
        assert ev.status == TaskStatus.TRANSCRIBING
        assert ev.progress == 0.5
        assert ev.message == "Transcribing segment 3/8"
        assert ev.timestamp is not None

    def test_frozen(self) -> None:
        ev = ProgressEvent(
            task_id="t", status=TaskStatus.QUEUED, progress=0.0, message=""
        )
        with pytest.raises(FrozenInstanceError):
            ev.progress = 1.0  # type: ignore[misc]


class TestCancelToken:
    def test_initially_not_cancelled(self) -> None:
        token = CancelToken()
        assert not token.is_cancelled

    def test_cancel_sets_cancelled(self) -> None:
        token = CancelToken()
        token.cancel()
        assert token.is_cancelled

    def test_cancel_is_idempotent(self) -> None:
        token = CancelToken()
        token.cancel()
        token.cancel()  # should not raise
        assert token.is_cancelled

    def test_check_raises_when_cancelled(self) -> None:
        token = CancelToken()
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            token.check()

    def test_check_does_not_raise_when_active(self) -> None:
        token = CancelToken()
        token.check()  # should not raise

    def test_wait_if_requested_raises_when_cancelled(self) -> None:
        async def run() -> None:
            token = CancelToken()
            token.cancel()
            with pytest.raises(asyncio.CancelledError):
                await token.wait_if_requested()

        asyncio.run(run())

    def test_wait_if_requested_awaits_cancel(self) -> None:
        async def run() -> None:
            token = CancelToken()

            async def cancel_after_delay() -> None:
                await asyncio.sleep(0.01)
                token.cancel()

            with pytest.raises(asyncio.CancelledError):
                await asyncio.gather(token.wait_if_requested(), cancel_after_delay())

        asyncio.run(run())
