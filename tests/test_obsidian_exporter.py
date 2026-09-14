"""Tests for the Obsidian exporter — atomic writes, attachments, idempotency."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from evey2obs.exporters.obsidian import ObsidianExporter
from evey2obs.models import ContentDocument, ImageRef, SummaryResult
from evey2obs.protocols import Exporter
from evey2obs.settings import ObsidianSettings

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def vault_path(tmp_path: Path) -> Path:
    """Create a temporary vault root."""
    v = tmp_path / "vault"
    v.mkdir()
    return v


@pytest.fixture
def obsidian_settings(vault_path: Path) -> ObsidianSettings:
    return ObsidianSettings(
        vault_path=str(vault_path),
        subdir="Inbox/evey2obs",
        attachment_subdir="_attachments/evey2obs",
    )


@pytest.fixture
def exporter(obsidian_settings: ObsidianSettings) -> ObsidianExporter:
    return ObsidianExporter(obsidian_settings)


# ── Init tests ───────────────────────────────────────────────────────────────


class TestObsidianExporterInit:
    def test_implements_exporter_protocol(
        self, exporter: ObsidianExporter
    ) -> None:
        assert isinstance(exporter, Exporter)

    def test_requires_vault_path(self) -> None:
        with pytest.raises(ValueError, match="vault path"):
            ObsidianExporter(ObsidianSettings(vault_path=""))

    def test_raises_on_nonexistent_vault(self, tmp_path: Path) -> None:
        missing = tmp_path / "ghost"
        with pytest.raises(FileNotFoundError):
            ObsidianExporter(ObsidianSettings(vault_path=str(missing)))

    def test_creates_subdirs(
        self, vault_path: Path, exporter: ObsidianExporter
    ) -> None:
        inbox = vault_path / "Inbox" / "evey2obs"
        attachments = vault_path / "_attachments" / "evey2obs"
        assert inbox.is_dir()
        assert attachments.is_dir()


# ── Export tests ─────────────────────────────────────────────────────────────


class TestObsidianExporterExport:
    async def test_export_creates_note_file(
        self,
        exporter: ObsidianExporter,
        sample_document: ContentDocument,
        sample_summary: SummaryResult,
    ) -> None:
        result = await exporter.export(sample_document, sample_summary)
        assert result.note_path.endswith(".md")

    async def test_export_returns_export_result(
        self,
        exporter: ObsidianExporter,
        sample_document: ContentDocument,
        sample_summary: SummaryResult,
    ) -> None:
        result = await exporter.export(sample_document, sample_summary)
        assert result.note_path == "Inbox/evey2obs/测试视频标题.md"
        assert result.obsidian_uri is not None
        assert result.obsidian_uri.startswith("obsidian://open?vault=")

    async def test_note_file_contains_expected_content(
        self,
        exporter: ObsidianExporter,
        sample_document: ContentDocument,
        sample_summary: SummaryResult,
        vault_path: Path,
    ) -> None:
        await exporter.export(sample_document, sample_summary)
        note_path = vault_path / "Inbox" / "evey2obs" / "测试视频标题.md"
        content = note_path.read_text(encoding="utf-8")
        assert "title: 测试视频标题" in content
        assert "platform: bilibili" in content
        assert "## 一句话总结" in content
        assert "这是一句话总结。" in content
        assert "## 核心要点" in content
        assert "## 详细笔记" in content
        assert "## 行动项" in content
        assert "## 时间轴 / 关键引用" in content
        assert "## 原始正文 / 完整转写" in content
        assert "## 来源与处理说明" in content

    async def test_note_filename_sanitizes_special_chars(
        self,
        exporter: ObsidianExporter,
        sample_document: ContentDocument,
        sample_summary: SummaryResult,
    ) -> None:
        doc = ContentDocument(
            id=sample_document.id,
            source_type=sample_document.source_type,
            content_type=sample_document.content_type,
            source_url=sample_document.source_url,
            canonical_url=sample_document.canonical_url,
            title="Title: with /slashes? and *stars*",
        )
        result = await exporter.export(doc, sample_summary)
        filename = result.note_path.split("/")[-1]
        assert ":" not in filename
        assert "?" not in filename
        assert "*" not in filename

    async def test_atomic_write_no_partial_file(
        self,
        exporter: ObsidianExporter,
        sample_document: ContentDocument,
        sample_summary: SummaryResult,
        vault_path: Path,
    ) -> None:
        await exporter.export(sample_document, sample_summary)
        note_path = vault_path / "Inbox" / "evey2obs" / "测试视频标题.md"
        assert note_path.exists()
        content = note_path.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "## 原始正文 / 完整转写" in content
        assert "## 来源与处理说明" in content


# ── Attachment tests ─────────────────────────────────────────────────────────


class TestAttachmentExport:
    async def test_copies_image_to_attachment_dir(
        self,
        exporter: ObsidianExporter,
        sample_document: ContentDocument,
        sample_summary: SummaryResult,
        vault_path: Path,
    ) -> None:
        # Create a real temp image file
        tmp_img = Path(tempfile.mkdtemp()) / "photo.jpg"
        tmp_img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")

        doc = ContentDocument(
            id=sample_document.id,
            source_type=sample_document.source_type,
            content_type=sample_document.content_type,
            source_url=sample_document.source_url,
            canonical_url=sample_document.canonical_url,
            title=sample_document.title,
            images=(
                ImageRef(
                    url="https://example.com/photo.jpg",
                    local_path=str(tmp_img),
                ),
            ),
        )

        result = await exporter.export(doc, sample_summary)
        assert len(result.attachment_paths) == 1
        assert "photo.jpg" in result.attachment_paths[0]

        # Verify file was copied
        dest = vault_path / "_attachments" / "evey2obs" / "photo.jpg"
        assert dest.exists()
        assert dest.read_bytes() == b"\xff\xd8\xff\xe0\x00\x10JFIF"

    async def test_url_only_image_not_copied(
        self,
        exporter: ObsidianExporter,
        sample_document: ContentDocument,
        sample_summary: SummaryResult,
    ) -> None:
        doc = ContentDocument(
            id=sample_document.id,
            source_type=sample_document.source_type,
            content_type=sample_document.content_type,
            source_url=sample_document.source_url,
            canonical_url=sample_document.canonical_url,
            title=sample_document.title,
            images=(ImageRef(url="https://example.com/remote.jpg"),),
        )
        result = await exporter.export(doc, sample_summary)
        assert result.attachment_paths == ()


# ── Idempotency tests ────────────────────────────────────────────────────────


class TestExportIdempotency:
    async def test_overwrite_existing_note(
        self,
        exporter: ObsidianExporter,
        sample_document: ContentDocument,
        sample_summary: SummaryResult,
    ) -> None:
        await exporter.export(sample_document, sample_summary)
        result = await exporter.export(sample_document, sample_summary)
        assert result.note_path == "Inbox/evey2obs/测试视频标题.md"

    async def test_different_content_different_filename(
        self,
        exporter: ObsidianExporter,
        sample_document: ContentDocument,
        sample_summary: SummaryResult,
    ) -> None:
        doc1 = ContentDocument(
            id=sample_document.id,
            source_type=sample_document.source_type,
            content_type=sample_document.content_type,
            source_url=sample_document.source_url,
            canonical_url=sample_document.canonical_url,
            title="Note One",
        )
        doc2 = ContentDocument(
            id=sample_document.id,
            source_type=sample_document.source_type,
            content_type=sample_document.content_type,
            source_url=sample_document.source_url,
            canonical_url=sample_document.canonical_url,
            title="Note Two",
        )
        r1 = await exporter.export(doc1, sample_summary)
        r2 = await exporter.export(doc2, sample_summary)
        assert r1.note_path != r2.note_path
