"""Whisper-based speech-to-text transcription.

Implements the :class:`~evey2obs.protocols.Transcriber` protocol.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path

from evey2obs.errors import Evey2ObsError
from evey2obs.events import CancelToken
from evey2obs.models import ErrorCode, ExtractedText, ExtractionMethod, Segment
from evey2obs.processors.media import MediaProcessor
from evey2obs.protocols import Transcriber
from evey2obs.settings import AppSettings

logger = logging.getLogger(__name__)

# Extended video suffixes that should have audio extracted before transcription
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv"}


class TranscriptionProcessor(Transcriber):
    """Transcribe audio/video media using OpenAI Whisper (local).

    Implements the :class:`~evey2obs.protocols.Transcriber` protocol.

    The Whisper model is lazy-loaded on the first :meth:`transcribe` call.
    """

    def __init__(
        self,
        settings: AppSettings,
        media_processor: MediaProcessor | None = None,
    ) -> None:
        self._settings = settings
        self._media_proc = media_processor
        self._model = None  # Lazy-loaded
        self._cancel_flag = False

    # ── Protocol ──────────────────────────────────────────────────────────

    async def transcribe(
        self,
        media: TemporaryMedia,  # noqa: F821
        cancel_token: CancelToken | None = None,
    ) -> ExtractedText:
        """Transcribe media and return timestamped text.

        Video files have audio extracted first via :class:`MediaProcessor`.
        """

        audio_path = Path(media.file_path)

        # Extract audio if needed
        suffix = audio_path.suffix.lower()
        if suffix in VIDEO_SUFFIXES:
            proc = self._ensure_media_processor()
            audio_path = await proc.extract_audio(audio_path, cancel_token)

        if cancel_token is not None:
            cancel_token.check()

        # Check cache (FR-014)
        segments = self._read_cache(audio_path)
        if segments is not None:
            logger.debug("Using cached transcription for: %s", audio_path)
        else:
            # Transcribe
            segments = await self._transcribe_file(audio_path, cancel_token)
            self._write_cache(audio_path, segments)

        # Build full text
        full_text = " ".join(s.text for s in segments)
        if not full_text.strip():
            raise Evey2ObsError(
                code=ErrorCode.NO_SPEECH,
                message="No speech detected in audio",
                detail=f"Audio file: {audio_path}",
            )

        return ExtractedText(
            text=full_text,
            segments=tuple(segments),
            extraction_method=ExtractionMethod.WHISPER,
        )

    def cancel(self) -> None:
        """Set internal cancel flag."""
        self._cancel_flag = True

    # ── Internal ──────────────────────────────────────────────────────────

    def _ensure_media_processor(self) -> MediaProcessor:
        if self._media_proc is None:
            self._media_proc = MediaProcessor(
                temp_dir=Path(self._settings.obsidian.vault_path or "/tmp")
                / ".evey2obs_temp"
            )
        return self._media_proc

    def _load_model(self) -> None:
        """Lazy-load the Whisper model."""
        if self._model is not None:
            return

        try:
            import whisper
        except ImportError as exc:
            raise Evey2ObsError(
                code=ErrorCode.CONTENT_UNAVAILABLE,
                message=(
                    "openai-whisper is not installed. "
                    "Run: pip install openai-whisper"
                ),
                detail=str(exc),
                recoverable=True,
            ) from exc

        model_name = self._settings.whisper_model
        try:
            self._model = whisper.load_model(model_name)
        except Exception as exc:
            raise Evey2ObsError(
                code=ErrorCode.DISK_FULL,
                message=f"Failed to load Whisper model '{model_name}'",
                detail=str(exc),
                recoverable=True,
            ) from exc

    async def _transcribe_file(
        self, audio_path: Path, cancel_token: CancelToken | None = None
    ) -> list[Segment]:
        """Run Whisper transcription in a thread."""
        self._load_model()

        def _run() -> list[dict[str, float | str]]:
            result = self._model.transcribe(  # type: ignore[union-attr]
                str(audio_path),
                language=None,
                verbose=False,
            )
            return result.get("segments", [])

        try:
            raw_segments = await asyncio.to_thread(_run)
        except Exception as exc:
            raise Evey2ObsError(
                code=ErrorCode.ASR_LOW_CONFIDENCE,
                message="Whisper transcription failed",
                detail=str(exc),
            ) from exc

        segments: list[Segment] = []
        for seg in raw_segments:
            if cancel_token is not None and cancel_token.is_cancelled:
                raise asyncio.CancelledError("Task cancelled")
            segments.append(
                Segment(
                    start=float(seg["start"]),
                    end=float(seg["end"]),
                    text=str(seg["text"]).strip(),
                )
            )

        return segments

    # ── Cache (content-hash based) ────────────────────────────────────────

    @staticmethod
    def _cache_key(audio_path: Path) -> str:
        """SHA-256 of the audio file content."""
        hasher = hashlib.sha256()
        with open(audio_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def _cache_path(audio_path: Path) -> Path:
        """Path to the JSON cache file for a given audio file."""
        key = TranscriptionProcessor._cache_key(audio_path)
        cache_dir = audio_path.parent / ".evey2obs_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{key}.json"

    def _read_cache(self, audio_path: Path) -> list[Segment] | None:
        cache_file = self._cache_path(audio_path)
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return [Segment(**s) for s in data["segments"]]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _write_cache(self, audio_path: Path, segments: list[Segment]) -> None:
        cache_file = self._cache_path(audio_path)
        try:
            segments_data = [
                {"start": s.start, "end": s.end, "text": s.text} for s in segments
            ]
            cache_file.write_text(
                json.dumps(
                    {"segments": segments_data},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass  # Non-critical
