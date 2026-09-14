"""Local pending exports / draft resilience manager.

When an export to an Obsidian Vault fails (e.g. vault directory does not exist,
drive unmounted, permission denied), the document and summary are preserved
as a local draft.  Users can list and retry exports without repeating media
download, Whisper transcription, or LLM summarization.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from evey2obs.errors import Evey2ObsError
from evey2obs.models import (
    ContentDocument,
    ContentType,
    ErrorCode,
    ExportResult,
    ExtractionMethod,
    ImageRef,
    Segment,
    SourceType,
    SummaryResult,
)
from evey2obs.protocols import Exporter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PendingExportSummary:
    """Lightweight metadata for UI / CLI listing of pending exports."""

    id: str
    title: str
    source_type: str
    content_type: str
    created_at: str
    error_message: str | None = None


def default_pending_export_dir(environ: Mapping[str, str] | None = None) -> Path:
    """Return platform-specific default directory for pending drafts."""
    env = environ if environ is not None else os.environ
    override = env.get("EVEY2OBS_RECOVERY_DIR", "").strip()
    if override:
        return Path(override).expanduser() / "pending-exports"
    if sys.platform == "win32":
        root = env.get("LOCALAPPDATA", "").strip()
        base = Path(root).expanduser() if root else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        root = env.get("XDG_DATA_HOME", "").strip()
        base = Path(root).expanduser() if root else Path.home() / ".local" / "share"
    return base / "evey2obs" / "pending-exports"


class PendingExportsManager:
    """Manages drafts preserved when vault export fails."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = (storage_dir or default_pending_export_dir()).expanduser()

    def save(
        self,
        document: ContentDocument,
        summary: SummaryResult,
        error_message: str | None = None,
    ) -> str:
        """Save document, summary, and attachments to a local draft folder."""
        recovery_id = uuid.uuid4().hex
        draft_dir = self.storage_dir / recovery_id
        draft_dir.mkdir(parents=True, exist_ok=True)

        # Copy any local images into the draft directory so they survive media cleanup
        saved_images: list[ImageRef] = []
        attachments_dir = draft_dir / "attachments"
        for img in document.images:
            if img.local_path and Path(img.local_path).exists():
                attachments_dir.mkdir(parents=True, exist_ok=True)
                dest = attachments_dir / Path(img.local_path).name
                try:
                    shutil.copy2(img.local_path, dest)
                    saved_images.append(
                        ImageRef(
                            url=img.url,
                            local_path=str(dest),
                            caption=img.caption,
                        )
                    )
                except OSError:
                    saved_images.append(img)
            else:
                saved_images.append(img)

        doc_dict = {
            "id": document.id,
            "source_type": document.source_type.value,
            "content_type": document.content_type.value,
            "source_url": document.source_url,
            "canonical_url": document.canonical_url,
            "title": document.title,
            "author": document.author,
            "published_at": document.published_at.isoformat() if document.published_at else None,
            "duration_seconds": document.duration_seconds,
            "description": document.description,
            "extraction_method": document.extraction_method.value,
            "text": document.text,
            "segments": [asdict(seg) for seg in document.segments],
            "images": [asdict(img) for img in saved_images],
            "summary": document.summary,
            "key_points": list(document.key_points),
            "action_items": list(document.action_items),
            "tags": list(document.tags),
            "warnings": list(document.warnings),
        }

        sum_dict = {
            "one_line_summary": summary.one_line_summary,
            "key_points": list(summary.key_points),
            "detailed_notes": summary.detailed_notes,
            "action_items": list(summary.action_items),
            "quotes": list(summary.quotes),
            "tags": list(summary.tags),
            "model_metadata": list(summary.model_metadata),
        }

        meta = {
            "recovery_id": recovery_id,
            "created_at": datetime.now(UTC).isoformat(),
            "error_message": error_message,
            "document": doc_dict,
            "summary": sum_dict,
        }

        meta_path = draft_dir / "draft.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved pending export draft %s for '%s'", recovery_id, document.title)
        return recovery_id

    def list(self) -> list[PendingExportSummary]:
        """List all pending export drafts."""
        if not self.storage_dir.exists():
            return []

        results: list[PendingExportSummary] = []
        for path in self.storage_dir.iterdir():
            if path.is_dir() and (path / "draft.json").exists():
                try:
                    meta = json.loads((path / "draft.json").read_text(encoding="utf-8"))
                    doc = meta.get("document", {})
                    results.append(
                        PendingExportSummary(
                            id=meta.get("recovery_id", path.name),
                            title=doc.get("title") or "Untitled",
                            source_type=doc.get("source_type", "unknown"),
                            content_type=doc.get("content_type", "unknown"),
                            created_at=meta.get("created_at", ""),
                            error_message=meta.get("error_message"),
                        )
                    )
                except Exception as exc:
                    logger.debug("Failed to read draft %s: %s", path, exc)
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def load(self, recovery_id: str) -> tuple[ContentDocument, SummaryResult]:
        """Load document and summary from draft."""
        draft_file = self.storage_dir / recovery_id / "draft.json"
        if not draft_file.exists():
            raise Evey2ObsError(
                ErrorCode.CONTENT_UNAVAILABLE,
                f"待导出草稿不存在：{recovery_id}",
            )

        try:
            meta = json.loads(draft_file.read_text(encoding="utf-8"))
            d = meta["document"]
            s = meta["summary"]

            published = (
                datetime.fromisoformat(d["published_at"])
                if d.get("published_at")
                else None
            )
            segments = tuple(
                Segment(start=seg["start"], end=seg["end"], text=seg["text"])
                for seg in d.get("segments", [])
            )
            images = tuple(
                ImageRef(
                    url=img["url"],
                    local_path=img.get("local_path"),
                    caption=img.get("caption"),
                )
                for img in d.get("images", [])
            )

            document = ContentDocument(
                id=d["id"],
                source_type=SourceType(d["source_type"]),
                content_type=ContentType(d["content_type"]),
                source_url=d["source_url"],
                canonical_url=d["canonical_url"],
                title=d.get("title"),
                author=d.get("author"),
                published_at=published,
                duration_seconds=d.get("duration_seconds"),
                description=d.get("description"),
                extraction_method=ExtractionMethod(d.get("extraction_method", "whisper")),
                text=d.get("text", ""),
                segments=segments,
                images=images,
                summary=d.get("summary", ""),
                key_points=tuple(d.get("key_points", ())),
                action_items=tuple(d.get("action_items", ())),
                tags=tuple(d.get("tags", ())),
                warnings=tuple(d.get("warnings", ())),
            )

            summary = SummaryResult(
                one_line_summary=s.get("one_line_summary", ""),
                key_points=tuple(s.get("key_points", ())),
                detailed_notes=s.get("detailed_notes", ""),
                action_items=tuple(s.get("action_items", ())),
                quotes=tuple(s.get("quotes", ())),
                tags=tuple(s.get("tags", ())),
                model_metadata=tuple(
                    tuple(item) for item in s.get("model_metadata", ())
                ),
            )
            return (document, summary)
        except Exception as exc:
            raise Evey2ObsError(
                ErrorCode.CONTENT_UNAVAILABLE,
                f"读取待导出草稿失败：{exc}",
            ) from exc

    def remove(self, recovery_id: str) -> bool:
        """Remove a draft by ID."""
        draft_dir = self.storage_dir / recovery_id
        if draft_dir.exists() and draft_dir.is_dir():
            shutil.rmtree(draft_dir, ignore_errors=True)
            return True
        return False

    async def retry_export(
        self, recovery_id: str, exporter: Exporter
    ) -> ExportResult:
        """Retry exporting a draft to Obsidian. If successful, deletes the draft."""
        document, summary = self.load(recovery_id)
        result = await exporter.export(document, summary)
        self.remove(recovery_id)
        return result
