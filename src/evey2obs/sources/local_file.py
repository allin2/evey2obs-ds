"""Local file fallback adapter.

Handles local audio/video files imported directly by the user,
bypassing yt-dlp and platform network resolution entirely.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from evey2obs.models import (
    ContentType,
    ExtractedText,
    ResolvedSource,
    SourceInput,
    SourceMetadata,
    SourceType,
    TemporaryMedia,
)
from evey2obs.protocols import SourceAdapter

# File extensions for video vs audio content type inference
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac", ".opus"}


class LocalFileAdapter(SourceAdapter):
    """Adapter for locally-imported audio and video files.

    Implements the :class:`~evey2obs.protocols.SourceAdapter` protocol.
    Since local files have no online subtitles, ``extract_text`` always
    returns ``None`` (forcing the Whisper fallback path).
    """

    # ── Protocol ────────────────────────────────────────────────────────

    def can_handle(self, source_input: SourceInput) -> bool:
        """Return ``True`` if *source_input* has local file paths."""
        return bool(source_input.local_files)

    async def resolve(self, source_input: SourceInput) -> ResolvedSource:
        """Identify the local file as a source."""
        if not source_input.local_files:
            raise ValueError("No local files provided")

        path = Path(source_input.local_files[0])
        suffix = path.suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            ct = ContentType.VIDEO
        elif suffix in AUDIO_EXTENSIONS:
            ct = ContentType.AUDIO
        else:
            ct = ContentType.VIDEO  # default guess

        return ResolvedSource(
            source_type=SourceType.LOCAL_FILE,
            content_type=ct,
            canonical_url=f"file://{path.resolve()}",
            source_id=str(path.resolve()),
        )

    async def extract_metadata(self, source: ResolvedSource) -> SourceMetadata:
        """Return basic metadata from the local file."""
        path = Path(source.source_id)
        return SourceMetadata(
            title=path.stem,
            description=f"Local file: {path.name}",
        )

    async def extract_text(self, source: ResolvedSource) -> ExtractedText | None:
        """Local files have no subtitles -- always fall back to Whisper."""
        return None

    async def extract_media(self, source: ResolvedSource) -> TemporaryMedia | None:
        """Return the local file path as temporary media."""
        path = Path(source.source_id)
        if not path.exists():
            return None

        mime_type, _ = mimetypes.guess_type(str(path))
        return TemporaryMedia(
            file_path=str(path),
            media_type=mime_type or "",
        )
