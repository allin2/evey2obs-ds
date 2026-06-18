"""Temporary media cleanup after successful export.

Implements the :class:`~evey2obs.protocols.Cleaner` protocol.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from evey2obs.models import TemporaryMedia
from evey2obs.protocols import Cleaner

logger = logging.getLogger(__name__)


class MediaCleaner(Cleaner):
    """Deletes temporary audio/video files after successful export.

    Implements the :class:`~evey2obs.protocols.Cleaner` protocol.
    """

    def __init__(self, retention_hours: int = 24) -> None:
        self._retention_hours = retention_hours

    async def cleanup(self, media_items: list[TemporaryMedia]) -> None:
        """Delete each temporary media file.

        Missing files are silently skipped (idempotent).
        """
        for media in media_items:
            path = Path(media.file_path)
            try:
                if path.exists():
                    path.unlink()
                    logger.debug("Cleaned up: %s", path)
            except OSError as exc:
                logger.warning("Failed to clean up %s: %s", path, exc)

    @staticmethod
    async def cleanup_expired(temp_dir: Path, retention_hours: int) -> int:
        """Delete files in *temp_dir* older than *retention_hours*.

        Called at startup to clean stale files from crashed previous runs.

        Returns:
            Number of files deleted.
        """
        temp_dir = Path(temp_dir)
        if not temp_dir.is_dir():
            return 0

        now = time.time()
        cutoff = now - (retention_hours * 3600)
        deleted = 0

        for entry in temp_dir.iterdir():
            if entry.is_file():
                try:
                    mtime = entry.stat().st_mtime
                    if mtime < cutoff:
                        entry.unlink()
                        deleted += 1
                except OSError:
                    pass

        return deleted

    @staticmethod
    def _sync_cleanup_expired(temp_dir: Path, retention_hours: int) -> int:
        """Synchronous variant for use in CLI startup hooks."""
        import asyncio

        return asyncio.run(
            MediaCleaner.cleanup_expired(temp_dir, retention_hours)
        )
