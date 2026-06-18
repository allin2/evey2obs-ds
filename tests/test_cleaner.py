"""Tests for MediaCleaner — file cleanup and retention."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from evey2obs.cleaner import MediaCleaner
from evey2obs.models import TemporaryMedia
from evey2obs.protocols import Cleaner


class TestProtocolCompliance:
    def test_implements_cleaner_protocol(self) -> None:
        c = MediaCleaner()
        assert isinstance(c, Cleaner)


class TestCleanup:
    @pytest.mark.asyncio
    async def test_deletes_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "test1.wav"
        f2 = tmp_path / "test2.wav"
        f1.write_text("dummy")
        f2.write_text("dummy")

        c = MediaCleaner()
        await c.cleanup([
            TemporaryMedia(file_path=str(f1)),
            TemporaryMedia(file_path=str(f2)),
        ])
        assert not f1.exists()
        assert not f2.exists()

    @pytest.mark.asyncio
    async def test_missing_file_no_error(self, tmp_path: Path) -> None:
        c = MediaCleaner()
        await c.cleanup([
            TemporaryMedia(file_path=str(tmp_path / "nonexistent.wav")),
        ])
        # Should not raise

    @pytest.mark.asyncio
    async def test_idempotent(self, tmp_path: Path) -> None:
        f = tmp_path / "test.wav"
        f.write_text("dummy")

        c = MediaCleaner()
        await c.cleanup([TemporaryMedia(file_path=str(f))])
        await c.cleanup([TemporaryMedia(file_path=str(f))])
        # Neither call should raise


class TestCleanupExpired:
    def test_deletes_old_files(self, tmp_path: Path) -> None:
        # Create a temp dir with old files
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        old = media_dir / "old.wav"
        old.write_text("old")
        # Set mtime to 48 hours ago
        mtime = time.time() - 48 * 3600
        os.utime(str(old), (mtime, mtime))

        import asyncio

        deleted = asyncio.run(MediaCleaner.cleanup_expired(media_dir, retention_hours=24))
        assert deleted == 1
        assert not old.exists()

    def test_keeps_recent_files(self, tmp_path: Path) -> None:
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        recent = media_dir / "recent.wav"
        recent.write_text("fresh")
        # File just created, so it's within retention

        import asyncio

        deleted = asyncio.run(MediaCleaner.cleanup_expired(media_dir, retention_hours=24))
        assert deleted == 0
        assert recent.exists()

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        import asyncio

        deleted = asyncio.run(
            MediaCleaner.cleanup_expired(tmp_path / "ghost", retention_hours=24)
        )
        assert deleted == 0
