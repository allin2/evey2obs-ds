"""Tests for PendingExportsManager."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from evey2obs.exporters.pending_exports import PendingExportsManager
from evey2obs.models import (
    ContentDocument,
    ContentType,
    ExportResult,
    ExtractionMethod,
    ImageRef,
    SourceType,
    SummaryResult,
)


@pytest.fixture
def sample_doc(tmp_path: Path):
    dummy_img = tmp_path / "cover.jpg"
    dummy_img.write_bytes(b"dummy image")

    return ContentDocument(
        id="BV12345",
        source_type=SourceType.BILIBILI,
        content_type=ContentType.VIDEO,
        source_url="https://www.bilibili.com/video/BV12345",
        canonical_url="https://www.bilibili.com/video/BV12345",
        title="Test Video",
        author="Author",
        extraction_method=ExtractionMethod.WHISPER,
        text="Full transcribed text",
        images=(ImageRef(url="https://example.com/cover.jpg", local_path=str(dummy_img)),),
    )


@pytest.fixture
def sample_summary():
    return SummaryResult(
        one_line_summary="A test summary",
        key_points=("Point 1", "Point 2"),
        detailed_notes="Detailed notes here",
        action_items=("Action 1",),
        tags=("AI", "Test"),
    )


def test_save_and_list_drafts(tmp_path: Path, sample_doc, sample_summary):
    mgr = PendingExportsManager(tmp_path / "pending")
    draft_id = mgr.save(sample_doc, sample_summary, error_message="Vault write error")
    assert draft_id is not None

    drafts = mgr.list()
    assert len(drafts) == 1
    assert drafts[0].id == draft_id
    assert drafts[0].title == "Test Video"
    assert drafts[0].error_message == "Vault write error"


def test_load_and_remove_draft(tmp_path: Path, sample_doc, sample_summary):
    mgr = PendingExportsManager(tmp_path / "pending")
    draft_id = mgr.save(sample_doc, sample_summary)

    doc, summary = mgr.load(draft_id)
    assert doc.title == sample_doc.title
    assert doc.text == sample_doc.text
    assert summary.one_line_summary == sample_summary.one_line_summary
    assert len(doc.images) == 1
    # Local path should have been copied into draft directory
    assert Path(doc.images[0].local_path).exists()

    removed = mgr.remove(draft_id)
    assert removed is True
    assert len(mgr.list()) == 0


@pytest.mark.asyncio
async def test_retry_export(tmp_path: Path, sample_doc, sample_summary):
    mgr = PendingExportsManager(tmp_path / "pending")
    draft_id = mgr.save(sample_doc, sample_summary)

    mock_exporter = AsyncMock()
    mock_exporter.export.return_value = ExportResult(note_path="Notes/Test.md")

    result = await mgr.retry_export(draft_id, mock_exporter)
    assert result.note_path == "Notes/Test.md"
    mock_exporter.export.assert_awaited_once()

    # Draft should be automatically removed upon successful export
    assert len(mgr.list()) == 0
