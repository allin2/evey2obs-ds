"""Tests for GUI constants — verify all labels and messages are defined."""

from evey2obs.gui.constants import (
    ERROR_MESSAGES,
    PLATFORM_ICONS,
    PLATFORM_LABELS,
    STAGE_LABELS,
    WHISPER_MODEL_SIZES,
)
from evey2obs.models import ErrorCode, SourceType, TaskStatus


class TestStageLabels:
    def test_all_statuses_have_label(self) -> None:
        for status in TaskStatus:
            assert status in STAGE_LABELS, f"Missing label for {status}"
            assert STAGE_LABELS[status], f"Empty label for {status}"


class TestPlatformLabels:
    def test_all_platforms_have_label(self) -> None:
        for st in SourceType:
            assert st in PLATFORM_LABELS, f"Missing label for {st}"
            assert PLATFORM_LABELS[st]

    def test_all_platforms_have_icon(self) -> None:
        for st in SourceType:
            assert st in PLATFORM_ICONS


class TestErrorMessages:
    def test_all_error_codes_have_message(self) -> None:
        for code in ErrorCode:
            assert code in ERROR_MESSAGES, f"Missing message for {code}"
            assert ERROR_MESSAGES[code]


class TestWhisperSizes:
    def test_all_models_have_size(self) -> None:
        for model in ("tiny", "base", "small", "medium", "large"):
            assert model in WHISPER_MODEL_SIZES
