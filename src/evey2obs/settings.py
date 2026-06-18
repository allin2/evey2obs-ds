"""Typed application settings with environment variable loading and sanitization.

All sensitive fields (api_key, cookies) are masked in ``sanitized_dict()``
and ``__repr__`` so they never leak to logs, error messages, or test output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from evey2obs.errors import Evey2ObsError
from evey2obs.models import ErrorCode


@dataclass(frozen=True)
class LLMSettings:
    """User-configured LLM connection parameters.

    *api_key* is sensitive — use :meth:`sanitized_dict` to get a log-safe
    representation.
    """

    protocol: str = "openai"  # "openai" | "anthropic"
    base_url: str = ""
    api_key: str = ""
    model: str = ""

    def sanitized_dict(self) -> dict[str, str]:
        """Return a dict with *api_key* masked."""
        return {
            "protocol": self.protocol,
            "base_url": self.base_url,
            "api_key": "***" if self.api_key else "",
            "model": self.model,
        }

    def __repr__(self) -> str:
        d = self.sanitized_dict()
        return (
            f"LLMSettings(protocol={d['protocol']!r}, base_url={d['base_url']!r}, "
            f"api_key={d['api_key']!r}, model={d['model']!r})"
        )


@dataclass(frozen=True)
class ObsidianSettings:
    """Obsidian Vault output configuration."""

    vault_path: str = ""
    subdir: str = "Inbox/evey2obs"
    attachment_subdir: str = "_attachments/evey2obs"


@dataclass(frozen=True)
class AppSettings:
    """Top-level application settings aggregating all subsystems."""

    llm: LLMSettings = field(default_factory=LLMSettings)
    obsidian: ObsidianSettings = field(default_factory=ObsidianSettings)
    whisper_model: str = "small"
    proxy: str | None = None
    cookies_from_browser: str | None = None
    cookies_file: str | None = None
    log_level: str = "INFO"
    temp_retention_hours: int = 24

    # ── Factory ────────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> AppSettings:
        """Build settings from environment variables.

        Variable mapping::

            EVEY2OBS_LLM_PROTOCOL     → llm.protocol
            EVEY2OBS_LLM_BASE_URL     → llm.base_url
            EVEY2OBS_LLM_API_KEY      → llm.api_key
            EVEY2OBS_LLM_MODEL        → llm.model
            EVEY2OBS_OBSIDIAN_VAULT        → obsidian.vault_path
            EVEY2OBS_OBSIDIAN_SUBDIR       → obsidian.subdir
            EVEY2OBS_OBSIDIAN_ATTACHMENT_SUBDIR → obsidian.attachment_subdir
            EVEY2OBS_WHISPER_MODEL     → whisper_model
            EVEY2OBS_PROXY             → proxy
            EVEY2OBS_COOKIES_BROWSER   → cookies_from_browser
            EVEY2OBS_COOKIES_FILE      → cookies_file
            EVEY2OBS_LOG_LEVEL         → log_level
            EVEY2OBS_TEMP_RETENTION_HOURS → temp_retention_hours
        """
        env = environ if environ is not None else dict(os.environ)

        def _get(key: str, default: str = "") -> str:
            return env.get(key, default)

        return cls(
            llm=LLMSettings(
                protocol=_get("EVEY2OBS_LLM_PROTOCOL", "openai"),
                base_url=_get("EVEY2OBS_LLM_BASE_URL", ""),
                api_key=_get("EVEY2OBS_LLM_API_KEY", ""),
                model=_get("EVEY2OBS_LLM_MODEL", ""),
            ),
            obsidian=ObsidianSettings(
                vault_path=_get("EVEY2OBS_OBSIDIAN_VAULT", ""),
                subdir=_get("EVEY2OBS_OBSIDIAN_SUBDIR", "Inbox/evey2obs"),
                attachment_subdir=_get(
                    "EVEY2OBS_OBSIDIAN_ATTACHMENT_SUBDIR", "_attachments/evey2obs"
                ),
            ),
            whisper_model=_get("EVEY2OBS_WHISPER_MODEL", "small"),
            proxy=_get("EVEY2OBS_PROXY", "") or None,
            cookies_from_browser=_get("EVEY2OBS_COOKIES_BROWSER", "") or None,
            cookies_file=_get("EVEY2OBS_COOKIES_FILE", "") or None,
            log_level=_get("EVEY2OBS_LOG_LEVEL", "INFO"),
            temp_retention_hours=int(
                _get("EVEY2OBS_TEMP_RETENTION_HOURS", "24")
            ),
        )

    # ── Validation ─────────────────────────────────────────────────────────

    def validate(self) -> list[Evey2ObsError]:
        """Validate all settings and return a list of problems.

        An empty list means settings are valid.
        """
        problems: list[Evey2ObsError] = []

        if self.obsidian.vault_path:
            vault = Path(self.obsidian.vault_path).expanduser().resolve()
            if not vault.exists():
                problems.append(
                    Evey2ObsError(
                        code=ErrorCode.DISK_FULL,
                        message=f"Obsidian vault path does not exist: {vault}",
                        recoverable=True,
                    )
                )
            elif not vault.is_dir():
                problems.append(
                    Evey2ObsError(
                        code=ErrorCode.DISK_FULL,
                        message=f"Obsidian vault path is not a directory: {vault}",
                        recoverable=True,
                    )
                )
            else:
                # Check writability
                test_file = vault / ".evey2obs_write_test"
                try:
                    test_file.touch()
                    test_file.unlink()
                except OSError as exc:
                    problems.append(
                        Evey2ObsError(
                            code=ErrorCode.DISK_FULL,
                            message=f"Cannot write to Obsidian vault: {vault}",
                            detail=str(exc),
                            recoverable=True,
                        )
                    )

        return problems

    # ── Sanitization ───────────────────────────────────────────────────────

    def sanitized_dict(self) -> dict[str, object]:
        """Return a log-safe dictionary with API keys masked."""
        return {
            "llm": self.llm.sanitized_dict(),
            "obsidian": {
                "vault_path": self.obsidian.vault_path,
                "subdir": self.obsidian.subdir,
                "attachment_subdir": self.obsidian.attachment_subdir,
            },
            "whisper_model": self.whisper_model,
            "proxy": self.proxy,
            "cookies_from_browser": "***" if self.cookies_from_browser else None,
            "cookies_file": "***" if self.cookies_file else None,
            "log_level": self.log_level,
            "temp_retention_hours": self.temp_retention_hours,
        }

    def __repr__(self) -> str:
        d = self.sanitized_dict()
        return f"AppSettings({d!r})"
