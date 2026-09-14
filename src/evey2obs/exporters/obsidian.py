"""Obsidian vault exporter implementing the ``Exporter`` protocol.

Uses two-phase atomic writes: content is written to a temporary file first,
verified, then atomically renamed to the final path.  This guarantees that
a partially-written note never appears under the final filename.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from evey2obs.exporters.markdown import render_note
from evey2obs.models import ContentDocument, ExportResult, SummaryResult
from evey2obs.protocols import Exporter
from evey2obs.settings import ObsidianSettings


class ObsidianExporter(Exporter):
    """Export content documents as Obsidian Markdown notes with attachments.

    Implements the :class:`~evey2obs.protocols.Exporter` protocol.
    """

    def __init__(self, settings: ObsidianSettings) -> None:
        if not settings.vault_path:
            raise ValueError("Obsidian vault path is not configured")

        vault_root = Path(settings.vault_path).expanduser().resolve()
        if not vault_root.exists():
            raise FileNotFoundError(f"Vault path does not exist: {vault_root}")
        if not vault_root.is_dir():
            raise NotADirectoryError(f"Vault path is not a directory: {vault_root}")

        # Verify writability
        test_file = vault_root / ".evey2obs_write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except OSError as exc:
            raise PermissionError(
                f"Cannot write to vault: {vault_root}"
            ) from exc

        self._vault_root = vault_root

        # Ensure output directories exist
        self._subdir = vault_root / settings.subdir
        self._attachment_subdir = vault_root / settings.attachment_subdir
        self._subdir.mkdir(parents=True, exist_ok=True)
        self._attachment_subdir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────

    async def export(
        self, document: ContentDocument, summary: SummaryResult
    ) -> ExportResult:
        """Render and atomically write a note with attachments.

        Returns an :class:`ExportResult` with paths relative to the vault root.
        """
        # 1. Render markdown
        rendered = render_note(document, summary)

        # 2. Atomic write of the note
        filename = self._sanitize_filename(document.title or "Untitled") + ".md"
        note_path = self._subdir / filename
        self._atomic_write(note_path, rendered)

        # 3. Copy attachments
        attachment_paths: list[str] = []
        for img in document.images:
            if img.local_path:
                src = Path(img.local_path)
                if src.exists():
                    dest_name = src.name
                    dest = self._attachment_subdir / dest_name
                    self._copy_attachment(src, dest)
                    vault_rel = str(
                        Path(self._attachment_subdir.name) / dest_name
                    )
                    attachment_paths.append(vault_rel)

        # 4. Build result with vault-relative paths for the note
        try:
            vault_rel_note = str(
                note_path.relative_to(self._vault_root)
            )
        except ValueError:
            vault_rel_note = str(note_path)

        # 5. Build Obsidian protocol URI (obsidian://open?vault=...&file=...)
        import urllib.parse
        vault_name = urllib.parse.quote(self._vault_root.name)
        file_encoded = urllib.parse.quote(vault_rel_note)
        obsidian_uri = f"obsidian://open?vault={vault_name}&file={file_encoded}"

        return ExportResult(
            note_path=vault_rel_note,
            attachment_paths=tuple(attachment_paths),
            obsidian_uri=obsidian_uri,
        )

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _sanitize_filename(title: str) -> str:
        """Replace filesystem-invalid characters in a note filename."""
        # Remove characters unsafe on macOS / Windows / Linux
        sanitized = re.sub(r'[\\/:*?"<>|]', "-", title)
        # Collapse multiple dashes
        sanitized = re.sub(r"-{2,}", "-", sanitized)
        # Strip leading/trailing whitespace and dashes
        sanitized = sanitized.strip(" -")
        return sanitized or "Untitled"

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Write *content* to *path* using a temp-file + rename strategy."""
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp.md", prefix="." + path.stem + "_", dir=str(parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.rename(tmp_path, str(path))
        except BaseException:
            # Clean up temp file on any failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _copy_attachment(src: Path, dest: Path) -> None:
        """Copy an attachment file with two-phase write."""
        dest.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            suffix=dest.suffix, prefix="." + dest.stem + "_", dir=str(dest.parent)
        )
        try:
            os.close(fd)
            shutil.copy2(src, tmp_path)
            os.rename(tmp_path, str(dest))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
