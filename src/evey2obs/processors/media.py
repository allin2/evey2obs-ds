"""ffmpeg wrapper for audio extraction, duration probing, and diagnostics.

All ffmpeg interaction is via subprocess — no pip dependency needed.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path

from evey2obs.errors import Evey2ObsError
from evey2obs.events import CancelToken
from evey2obs.models import ErrorCode


@dataclass(frozen=True)
class FFmpegInfo:
    """Result of probing the system ffmpeg installation."""

    available: bool
    version: str | None = None
    path: str | None = None


class MediaProcessor:
    """Extract audio and probe media duration using the system ffmpeg binary."""

    def __init__(self, temp_dir: Path) -> None:
        self._temp_dir = Path(temp_dir)
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    # ── Diagnostics ──────────────────────────────────────────────────────

    @staticmethod
    def check_ffmpeg() -> FFmpegInfo:
        """Check whether ffmpeg is available on PATH."""
        import subprocess  # noqa: S404 – intentional subprocess for system binary

        path = shutil.which("ffmpeg")
        if path is None:
            return FFmpegInfo(available=False)
        try:
            result = subprocess.run(
                [path, "-version"], capture_output=True, text=True, timeout=10
            )
            version_line = result.stdout.split("\n")[0] if result.stdout else None
            return FFmpegInfo(
                available=result.returncode == 0,
                version=version_line,
                path=str(path),
            )
        except (OSError, subprocess.TimeoutExpired):
            return FFmpegInfo(available=False)

    # ── Audio extraction ─────────────────────────────────────────────────

    async def extract_audio(
        self, source: Path, cancel_token: CancelToken | None = None
    ) -> Path:
        """Extract audio track as 16kHz mono WAV via ffmpeg.

        Args:
            source: Path to a video or audio file.
            cancel_token: Optional cancellation token checked before starting.

        Returns:
            Path to the extracted WAV file in *temp_dir*.
        """
        if cancel_token is not None:
            cancel_token.check()

        source = Path(source).resolve()
        if not source.exists():
            raise Evey2ObsError(
                code=ErrorCode.CONTENT_UNAVAILABLE,
                message=f"Media file not found: {source}",
                recoverable=False,
            )

        output = self._temp_dir / f"{source.stem}_audio.wav"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err_text = stderr.decode("utf-8", errors="replace")[-500:]
                raise Evey2ObsError(
                    code=ErrorCode.ASR_LOW_CONFIDENCE,
                    message="ffmpeg audio extraction failed",
                    detail=err_text,
                    recoverable=False,
                )
        except Evey2ObsError:
            raise
        except OSError as exc:
            raise Evey2ObsError(
                code=ErrorCode.CONTENT_UNAVAILABLE,
                message="ffmpeg not found or not executable",
                detail=str(exc),
                recoverable=True,
            ) from exc

        return output

    # ── Duration probing ─────────────────────────────────────────────────

    async def get_duration(self, source: Path) -> float:
        """Probe media duration in seconds via ffprobe.

        Returns:
            Duration as float. Raises ``Evey2ObsError`` on failure.
        """
        source = Path(source).resolve()
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(source),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await proc.communicate()

            if proc.returncode != 0:
                raise Evey2ObsError(
                    code=ErrorCode.ASR_LOW_CONFIDENCE,
                    message="ffprobe duration probe failed",
                    recoverable=False,
                )

            return float(stdout.decode("utf-8").strip())
        except ValueError as exc:
            raise Evey2ObsError(
                code=ErrorCode.ASR_LOW_CONFIDENCE,
                message="Could not parse media duration",
                detail=str(exc),
                recoverable=False,
            ) from exc
        except OSError as exc:
            raise Evey2ObsError(
                code=ErrorCode.CONTENT_UNAVAILABLE,
                message="ffprobe not found or not executable",
                detail=str(exc),
                recoverable=True,
            ) from exc
