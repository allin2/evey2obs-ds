"""Tests for ProcessingPipeline — task creation, progress, and cancellation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from evey2obs.models import (
    SourceInput,
    TaskStatus,
)
from evey2obs.pipeline import ProcessingPipeline
from evey2obs.settings import AppSettings


@pytest.fixture
def pipeline() -> ProcessingPipeline:
    return ProcessingPipeline(AppSettings())


class TestPipelineSubmit:
    def test_submit_creates_tasks(self, pipeline: ProcessingPipeline) -> None:
        si = SourceInput.from_urls(["https://www.bilibili.com/video/BV123"])
        with patch.object(pipeline, "_process_task"):
            import asyncio
            async def _run():
                return await pipeline.submit(si)
            tasks = asyncio.run(_run())
            assert len(tasks) == 1
            assert tasks[0].status == TaskStatus.QUEUED

    def test_submit_empty_input(self, pipeline: ProcessingPipeline) -> None:
        import asyncio
        async def _run():
            return await pipeline.submit(SourceInput())
        tasks = asyncio.run(_run())
        assert tasks == []

    def test_submit_from_raw_text(self, pipeline: ProcessingPipeline) -> None:
        with patch.object(pipeline, "_process_task"):
            import asyncio
            si = SourceInput(raw_text="Check: https://www.bilibili.com/video/BV123")
            async def _run():
                return await pipeline.submit(si)
            tasks = asyncio.run(_run())
            assert len(tasks) == 1

    def test_submit_deduplicates_explicit_and_raw_urls(
        self, pipeline: ProcessingPipeline
    ) -> None:
        with patch.object(pipeline, "_process_task"):
            import asyncio

            url = "https://www.youtube.com/watch?v=abc12345678"
            si = SourceInput(raw_text=url, urls=(url,))

            async def _run():
                return await pipeline.submit(si)

            tasks = asyncio.run(_run())
            assert len(tasks) == 1

    def test_submit_local_files(self, pipeline: ProcessingPipeline) -> None:
        with patch.object(pipeline, "_process_task"):
            import asyncio
            si = SourceInput.from_local_files(["audio.mp3"])
            async def _run():
                return await pipeline.submit(si)
            tasks = asyncio.run(_run())
            assert len(tasks) == 1


class TestPipelineCancel:
    def test_cancel_sets_cancelled(self, pipeline: ProcessingPipeline) -> None:
        with patch.object(pipeline, "_process_task"):
            import asyncio
            async def _run():
                si = SourceInput.from_urls(["https://b23.tv/test"])
                tasks = await pipeline.submit(si)
                await pipeline.cancel(tasks[0].id)
                assert tasks[0].status == TaskStatus.CANCELLED
            asyncio.run(_run())


class TestPipelineProgress:
    def test_progress_callback_registers(self, pipeline: ProcessingPipeline) -> None:
        events = []
        pipeline.on_progress(lambda ev: events.append(ev))
        assert len(pipeline._progress_callbacks) == 1

    def test_transition_updates_stage_progress(self, pipeline: ProcessingPipeline) -> None:
        from evey2obs.models import Task

        task = Task(id="test")
        pipeline._transition(task, TaskStatus.SUMMARIZING, "summarizing")
        assert task.progress == 0.7


class TestPipelineProcessTask:
    def test_internal_state_exists(self, pipeline: ProcessingPipeline) -> None:
        assert pipeline._tasks is not None
        assert pipeline._cancel_tokens is not None
        assert pipeline.transcript_cache is not None
        assert pipeline.pending_exports is not None

    def test_submit_with_options(self, pipeline: ProcessingPipeline) -> None:
        with patch.object(pipeline, "_process_task") as mock_process:
            import asyncio

            async def _run():
                si = SourceInput.from_urls(["https://b23.tv/BV123"])
                tasks = await pipeline.submit(
                    si, force_refresh=True, template="course"
                )
                assert len(tasks) == 1

            asyncio.run(_run())
            mock_process.assert_called_once()
            _, kwargs = mock_process.call_args
            assert kwargs["force_refresh"] is True
            assert kwargs["template"] == "course"
