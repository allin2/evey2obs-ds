"""Local disk cache for Whisper transcription results.

Prevents re-downloading media and re-running expensive Whisper transcription
when reprocessing URLs or running summaries with different templates.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from evey2obs.models import ExtractedText, ExtractionMethod, Segment, SourceType

logger = logging.getLogger(__name__)

_CACHE_VERSION = 1
_MAX_CACHE_BYTES = 32 * 1024 * 1024  # 32 MB per transcript


def default_cache_dir(environ: Mapping[str, str] | None = None) -> Path:
    """Return platform-specific default cache directory for transcripts."""
    env = environ if environ is not None else os.environ
    override = env.get("EVEY2OBS_CACHE_DIR", "").strip()
    if override:
        return Path(override).expanduser() / "transcripts"
    if sys.platform == "win32":
        root = env.get("LOCALAPPDATA", "").strip()
        base = Path(root).expanduser() if root else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        root = env.get("XDG_CACHE_HOME", "").strip()
        base = Path(root).expanduser() if root else Path.home() / ".cache"
    return base / "evey2obs" / "transcripts"


def _file_digest(path: Path) -> str | None:
    """Calculate SHA256 digest of a local file."""
    digest = hashlib.sha256()
    try:
        with path.expanduser().open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


class TranscriptionCache:
    """Disk-backed cache for reusable Whisper transcription results."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = (cache_dir or default_cache_dir()).expanduser()

    def _key(
        self,
        source_type: SourceType,
        source_id: str,
        model_name: str,
        file_path: Path | None = None,
    ) -> str | None:
        if source_type == SourceType.LOCAL_FILE:
            if file_path is None or not file_path.exists():
                return None
            digest = _file_digest(file_path)
            if digest is None:
                return None
            identity = f"local:{digest}"
        else:
            if not source_id:
                return None
            identity = f"{source_type.value}:{source_id}"

        material = f"v{_CACHE_VERSION}\0{model_name}\0{identity}".encode()
        return hashlib.sha256(material).hexdigest()

    def load(
        self,
        source_type: SourceType,
        source_id: str,
        model_name: str,
        file_path: Path | None = None,
    ) -> ExtractedText | None:
        """Load cached transcript if available, or return None."""
        key = self._key(source_type, source_id, model_name, file_path)
        if key is None:
            return None
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.is_file():
            return None

        try:
            if cache_file.stat().st_size > _MAX_CACHE_BYTES:
                return None
            data: dict[str, Any] = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("version") != _CACHE_VERSION or data.get("model") != model_name:
                return None

            segments = tuple(
                Segment(
                    start=float(item["start"]),
                    end=float(item["end"]),
                    text=str(item["text"]),
                )
                for item in data.get("segments", [])
                if isinstance(item, dict)
            )
            text = str(data.get("text", ""))
            if not text and not segments:
                return None

            logger.info(
                "Transcript cache HIT for %s:%s (%s)",
                source_type.value,
                source_id,
                model_name,
            )
            return ExtractedText(
                text=text,
                segments=segments,
                extraction_method=ExtractionMethod.CACHE,
            )
        except Exception as exc:
            logger.debug("Failed to read cache file %s: %s", cache_file, exc)
            return None

    def store(
        self,
        source_type: SourceType,
        source_id: str,
        model_name: str,
        extracted: ExtractedText,
        file_path: Path | None = None,
    ) -> bool:
        """Store transcript into cache."""
        if not extracted.text.strip():
            return False
        key = self._key(source_type, source_id, model_name, file_path)
        if key is None:
            return False

        payload = {
            "version": _CACHE_VERSION,
            "model": model_name,
            "text": extracted.text,
            "segments": [
                {"start": seg.start, "end": seg.end, "text": seg.text}
                for seg in extracted.segments
            ],
            "extraction_method": extracted.extraction_method.value,
        }

        cache_file = self.cache_dir / f"{key}.json"
        tmp_file = cache_file.with_name(f".{cache_file.name}.tmp")
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tmp_file.replace(cache_file)
            logger.info(
                "Transcript cache stored for %s:%s (%s)",
                source_type.value,
                source_id,
                model_name,
            )
            return True
        except OSError as exc:
            logger.warning("Failed to store transcript cache: %s", exc)
            tmp_file.unlink(missing_ok=True)
            return False

    def clear(self) -> int:
        """Remove all cached transcripts. Returns count of deleted files."""
        if not self.cache_dir.exists():
            return 0
        count = 0
        for item in self.cache_dir.glob("*.json"):
            try:
                item.unlink()
                count += 1
            except OSError:
                pass
        return count
