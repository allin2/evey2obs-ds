"""Structured error type for evey2obs.

All pipeline, adapter, and processor errors use a single exception class
parameterised by :class:`ErrorCode` so that the GUI and CLI can map errors
to stable, user-facing messages without inspecting exception chains.
"""

from __future__ import annotations

from dataclasses import dataclass

from evey2obs.models import ErrorCode


@dataclass
class Evey2ObsError(Exception):
    """Single structured exception for all evey2obs error paths.

    The *code* enum member determines the stable error identity; *message*
    is the human-readable summary.  *detail* may carry additional context
    (stack traces, raw responses, etc.) for diagnostic logs, but the GUI
    should not display *detail* by default.

    *recoverable* indicates whether the user can take action to resolve
    the error (e.g. re-copy a share link) rather than it being a permanent
    failure.
    """

    code: ErrorCode
    message: str
    detail: str | None = None
    recoverable: bool = True

    def __post_init__(self) -> None:
        # Populate BaseException.args so that exception grouping,
        # Sentry, and other tooling that inspects args gets the message.
        super().__init__(self.message)

    def __str__(self) -> str:
        base = f"[{self.code.value}] {self.message}"
        if self.detail:
            return f"{base} ({self.detail})"
        return base
