"""Shared base class for yt-dlp based platform adapters.

Provides subprocess management, VTT/SRT parsing, error mapping,
and the subtitle-first / Whisper-fallback strategy.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from pathlib import Path

from evey2obs.errors import Evey2ObsError
from evey2obs.events import CancelToken
from evey2obs.inputs import extract_urls, identify_source
from evey2obs.models import (
    ContentType,
    ErrorCode,
    ExtractedText,
    ExtractionMethod,
    ResolvedSource,
    Segment,
    SourceInput,
    SourceMetadata,
    SourceType,
    TemporaryMedia,
)
from evey2obs.protocols import SourceAdapter
from evey2obs.settings import AppSettings

logger = logging.getLogger(__name__)

# ── Subtitle parsers ────────────────────────────────────────────────────────

_VTT_TIMING = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
)
_SRT_TIMING = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def _timestamp_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _parse_vtt(path: Path) -> list[Segment]:
    """Parse WebVTT subtitle file into segments."""
    content = path.read_text(encoding="utf-8", errors="replace")
    segments: list[Segment] = []
    current_start: float | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue

        # Skip metadata/style headers
        if line.startswith("Kind:") or line.startswith("Language:"):
            continue

        m = _VTT_TIMING.match(line)
        if m:
            # Save previous segment
            if current_start is not None and current_lines:
                segments.append(
                    Segment(
                        start=current_start,
                        end=_timestamp_to_seconds(m.group(5), m.group(6), m.group(7), m.group(8)),
                        text=" ".join(current_lines),
                    )
                )
                current_lines = []
            current_start = _timestamp_to_seconds(
                m.group(1), m.group(2), m.group(3), m.group(4)
            )
        elif current_start is not None and line:
            # Remove VTT tags like <c> <00:00:01.000>
            clean = re.sub(r"<[^>]+>", "", line)
            if clean.strip():
                current_lines.append(clean.strip())

    # Last segment
    if current_start is not None and current_lines:
        segments.append(
            Segment(
                start=current_start,
                end=current_start + 5.0,  # best-effort end time
                text=" ".join(current_lines),
            )
        )

    return segments


def _parse_srt(path: Path) -> list[Segment]:
    """Parse SRT subtitle file into segments."""
    content = path.read_text(encoding="utf-8", errors="replace")
    segments: list[Segment] = []
    current_start: float | None = None
    current_end: float | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        line = line.strip()
        if not line:
            if current_start is not None and current_lines:
                segments.append(
                    Segment(
                        start=current_start,
                        end=current_end or current_start + 5.0,
                        text=" ".join(current_lines),
                    )
                )
                current_start = None
                current_end = None
                current_lines = []
            continue

        # Skip index numbers
        if line.isdigit():
            continue

        m = _SRT_TIMING.match(line)
        if m:
            current_start = _timestamp_to_seconds(
                m.group(1), m.group(2), m.group(3), m.group(4)
            )
            current_end = _timestamp_to_seconds(
                m.group(5), m.group(6), m.group(7), m.group(8)
            )
        elif current_start is not None:
            clean = re.sub(r"<[^>]+>", "", line)
            if clean.strip():
                current_lines.append(clean.strip())

    # Last segment
    if current_start is not None and current_lines:
        segments.append(
            Segment(
                start=current_start,
                end=current_end or current_start + 5.0,
                text=" ".join(current_lines),
            )
        )

    return segments


# ── Error pattern mapping ───────────────────────────────────────────────────

_ERROR_PATTERNS: list[tuple[str, ErrorCode, bool]] = [
    ("video is not available in your country", ErrorCode.CONTENT_UNAVAILABLE, False),
    ("video unavailable", ErrorCode.CONTENT_UNAVAILABLE, False),
    ("video is private", ErrorCode.CONTENT_UNAVAILABLE, False),
    ("sign in to confirm your age", ErrorCode.AUTH_REQUIRED, True),
    ("sign in", ErrorCode.AUTH_REQUIRED, True),
    ("login required", ErrorCode.AUTH_REQUIRED, True),
    ("http error 403", ErrorCode.CONTENT_UNAVAILABLE, False),
    ("http error 404", ErrorCode.CONTENT_UNAVAILABLE, False),
    ("http error 412", ErrorCode.AUTH_REQUIRED, True),
    ("this video is not available", ErrorCode.CONTENT_UNAVAILABLE, False),
    ("content unavailable", ErrorCode.CONTENT_UNAVAILABLE, False),
    ("removed", ErrorCode.CONTENT_UNAVAILABLE, False),
    ("deleted", ErrorCode.CONTENT_UNAVAILABLE, False),
    ("geo-restricted", ErrorCode.CONTENT_UNAVAILABLE, False),
]


def _classify_ytdlp_error(stderr: str) -> Evey2ObsError:
    """Map yt-dlp stderr output to a structured error."""
    stderr_lower = stderr.lower()
    for pattern, code, recoverable in _ERROR_PATTERNS:
        if pattern in stderr_lower:
            return Evey2ObsError(
                code=code,
                message=f"Platform error: {pattern}",
                detail=stderr.strip()[-500:],
                recoverable=recoverable,
            )
    return Evey2ObsError(
        code=ErrorCode.CONTENT_UNAVAILABLE,
        message="yt-dlp download failed",
        detail=stderr.strip()[-500:],
    )


# ── YtDlpAdapter ────────────────────────────────────────────────────────────


class YtDlpAdapter(SourceAdapter):
    """Base class for platform adapters that use yt-dlp.

    Subclasses define *source_type*, *domains*, *subtitle_langs*, and
    *auto_subs*.
    """

    def __init__(
        self,
        settings: AppSettings,
        *,
        source_type: SourceType,
        domains: list[str],
        subtitle_langs: list[str],
        auto_subs: bool = False,
    ) -> None:
        self._settings = settings
        self._source_type = source_type
        self._domains = domains
        self._subtitle_langs = subtitle_langs
        self._auto_subs = auto_subs
        self._temp_dir = Path(tempfile.mkdtemp(prefix="evey2obs_"))

    # ── Protocol ──────────────────────────────────────────────────────────

    def can_handle(self, source_input: SourceInput) -> bool:
        """Check if any URL in the input belongs to this adapter's domains."""
        all_urls = list(source_input.urls)
        if source_input.raw_text:
            all_urls.extend(extract_urls(source_input.raw_text))
        for url in all_urls:
            st = identify_source(url)
            if st is self._source_type:
                return True
        return False

    async def resolve(self, source_input: SourceInput) -> ResolvedSource:
        """Resolve short links and identify content type."""
        url = self._extract_matching_url(source_input)

        # Resolve short links via yt-dlp
        canonical = await self._resolve_url(url)

        source_id = self._extract_source_id(canonical)

        return ResolvedSource(
            source_type=self._source_type,
            content_type=ContentType.VIDEO,
            canonical_url=canonical,
            source_id=source_id,
        )

    async def extract_metadata(self, source: ResolvedSource) -> SourceMetadata:
        """Fetch metadata via yt-dlp --dump-json."""
        args = [
            source.canonical_url,
            "--dump-json",
            "--no-download",
            "--no-playlist",
        ]
        stdout = await self._run_ytdlp(args)
        data = json.loads(stdout)

        from datetime import datetime

        upload_date = data.get("upload_date")
        published = None
        if upload_date and len(upload_date) == 8:
            try:
                published = datetime.strptime(upload_date, "%Y%m%d")
            except ValueError:
                pass

        return SourceMetadata(
            title=data.get("title") or data.get("fulltitle"),
            author=data.get("uploader") or data.get("channel"),
            published_at=published,
            duration_seconds=data.get("duration"),
            description=data.get("description"),
        )

    async def extract_text(self, source: ResolvedSource) -> ExtractedText | None:
        """Download and parse subtitles if available."""
        args = [
            source.canonical_url,
            "--skip-download",
            "--no-playlist",
            "--write-subs" if not self._auto_subs else "--write-auto-subs",
            "--sub-format",
            "vtt/srt/ass",
            "--sub-langs",
            ",".join(self._subtitle_langs),
            "--output",
            str(self._temp_dir / "%(id)s.%(ext)s"),
        ]

        try:
            await self._run_ytdlp(args, timeout=60)
        except Evey2ObsError:
            return None

        # Find subtitle files in temp dir
        subtitle_files = sorted(
            list(self._temp_dir.glob("*.vtt")) + list(self._temp_dir.glob("*.srt")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not subtitle_files:
            return None

        sf = subtitle_files[0]
        segments = _parse_vtt(sf) if sf.suffix == ".vtt" else _parse_srt(sf)
        if not segments:
            return None

        full_text = " ".join(s.text for s in segments)
        return ExtractedText(
            text=full_text,
            segments=tuple(segments),
            extraction_method=ExtractionMethod.SUBTITLE,
        )

    async def extract_media(self, source: ResolvedSource) -> TemporaryMedia | None:
        """Download audio-only media for transcription."""
        output_tmpl = str(self._temp_dir / "%(id)s.%(ext)s")
        args = [
            source.canonical_url,
            "-f",
            "bestaudio[ext=m4a]/bestaudio/best",
            "--extract-audio",
            "--audio-format",
            "wav",
            "--audio-quality",
            "0",
            "--no-playlist",
            "--output",
            output_tmpl,
        ]

        await self._run_ytdlp(args, timeout=300)
        wav_files = sorted(self._temp_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime)
        if not wav_files:
            return None

        return TemporaryMedia(file_path=str(wav_files[0]), media_type="audio/wav")

    # ── Subprocess ────────────────────────────────────────────────────────

    async def _run_ytdlp(
        self,
        args: list[str],
        timeout: int = 120,
        cancel_token: CancelToken | None = None,
    ) -> str:
        """Run yt-dlp as a subprocess and return stdout.

        Maps known error patterns to structured :class:`Evey2ObsError`.
        """
        import sys
        yt_dlp_bin = str(Path(sys.executable).parent / "yt-dlp")
        deno_bin = str(Path.home() / ".deno/bin/deno")
        cmd = [yt_dlp_bin]
        if Path(deno_bin).exists():
            cmd.extend(["--js-runtimes", f"deno:{deno_bin}"])
        cmd.extend(args)

        # Add proxy if configured
        if self._settings.proxy:
            cmd.extend(["--proxy", self._settings.proxy])

        # Add cookies if configured
        if self._settings.cookies_file:
            cmd.extend(["--cookies", self._settings.cookies_file])
        elif self._settings.cookies_from_browser:
            cmd.extend(["--cookies-from-browser", self._settings.cookies_from_browser])

        logger.debug("Running: %s", " ".join(cmd))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except TimeoutError as err:
                proc.kill()
                await proc.wait()
                raise Evey2ObsError(
                    code=ErrorCode.CONTENT_UNAVAILABLE,
                    message="yt-dlp timed out",
                ) from err

            if proc.returncode != 0:
                err_text = stderr.decode("utf-8", errors="replace")
                raise _classify_ytdlp_error(err_text)

            return stdout.decode("utf-8", errors="replace")

        except FileNotFoundError as err:
            raise Evey2ObsError(
                code=ErrorCode.CONTENT_UNAVAILABLE,
                message="yt-dlp is not installed. Run: pip install yt-dlp",
                recoverable=True,
            ) from err
        except Evey2ObsError:
            raise
        except Exception as exc:
            raise Evey2ObsError(
                code=ErrorCode.CONTENT_UNAVAILABLE,
                message="yt-dlp execution failed",
                detail=str(exc),
            ) from exc

    # ── URL helpers ───────────────────────────────────────────────────────

    def _extract_matching_url(self, source_input: SourceInput) -> str:
        """Find the first URL that matches this adapter's source type."""
        all_urls = list(source_input.urls)
        if source_input.raw_text:
            all_urls.extend(extract_urls(source_input.raw_text))

        for url in all_urls:
            if identify_source(url) is self._source_type:
                return url

        raise Evey2ObsError(
            code=ErrorCode.SOURCE_UNSUPPORTED,
            message=f"No {self._source_type.value} URL found in input",
        )

    async def _resolve_url(self, url: str) -> str:
        """Resolve a short link to its canonical URL via yt-dlp."""
        args = [url, "--print", "final_url", "--no-download", "--no-playlist"]
        stdout = await self._run_ytdlp(args, timeout=30)
        canonical = stdout.strip()
        # yt-dlp returns "NA" when the URL is already canonical (e.g. YouTube)
        if not canonical or canonical == "NA":
            return url
        return canonical

    # ── Source ID extraction (override in subclasses) ─────────────────────

    def _extract_source_id(self, canonical_url: str) -> str:
        """Extract platform-specific content ID from the canonical URL.

        Subclasses should override this for platform-specific ID extraction.
        """
        raise NotImplementedError("Subclasses must implement _extract_source_id")
