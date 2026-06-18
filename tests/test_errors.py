"""Tests for structured error type."""

from __future__ import annotations

import pytest

from evey2obs.errors import Evey2ObsError
from evey2obs.models import ErrorCode


class TestEvey2ObsError:
    def test_is_exception_subclass(self) -> None:
        assert issubclass(Evey2ObsError, Exception)

    @pytest.mark.parametrize("code", list(ErrorCode))
    def test_create_with_each_code(self, code: ErrorCode) -> None:
        err = Evey2ObsError(code=code, message="test message")
        assert err.code == code
        assert err.message == "test message"

    def test_string_format_without_detail(self) -> None:
        err = Evey2ObsError(code=ErrorCode.INPUT_NO_URL, message="No URL found")
        assert str(err) == "[INPUT_NO_URL] No URL found"

    def test_string_format_with_detail(self) -> None:
        err = Evey2ObsError(
            code=ErrorCode.LLM_FAILED,
            message="Model request failed",
            detail="Connection refused",
        )
        assert str(err) == "[LLM_FAILED] Model request failed (Connection refused)"

    def test_default_recoverable(self) -> None:
        err = Evey2ObsError(code=ErrorCode.LLM_FAILED, message="x")
        assert err.recoverable is True

    def test_non_recoverable(self) -> None:
        err = Evey2ObsError(
            code=ErrorCode.CONTENT_UNAVAILABLE,
            message="Content deleted",
            recoverable=False,
        )
        assert err.recoverable is False

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(Evey2ObsError) as exc_info:
            raise Evey2ObsError(code=ErrorCode.DISK_FULL, message="No space left")
        assert exc_info.value.code == ErrorCode.DISK_FULL
        assert exc_info.value.message == "No space left"

    def test_detail_defaults_to_none(self) -> None:
        err = Evey2ObsError(code=ErrorCode.AUTH_REQUIRED, message="Login needed")
        assert err.detail is None
