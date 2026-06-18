"""Tests for settings module — loading, validation, and sanitization."""

from __future__ import annotations

import errno
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from evey2obs.models import ErrorCode
from evey2obs.settings import AppSettings, LLMSettings, ObsidianSettings

# ── LLMSettings ──────────────────────────────────────────────────────────────


class TestLLMSettings:
    def test_defaults(self) -> None:
        s = LLMSettings()
        assert s.protocol == "openai"
        assert s.base_url == ""
        assert s.api_key == ""
        assert s.model == ""

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EVEY2OBS_LLM_PROTOCOL", "anthropic")
        monkeypatch.setenv("EVEY2OBS_LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("EVEY2OBS_LLM_API_KEY", "sk-secret")
        monkeypatch.setenv("EVEY2OBS_LLM_MODEL", "claude-opus")

        app = AppSettings.from_env()
        assert app.llm.protocol == "anthropic"
        assert app.llm.base_url == "https://api.example.com"
        assert app.llm.api_key == "sk-secret"
        assert app.llm.model == "claude-opus"

    def test_api_key_masked_in_repr(self) -> None:
        s = LLMSettings(api_key="sk-abc123")
        r = repr(s)
        assert "sk-abc123" not in r
        assert "***" in r

    def test_api_key_masked_in_sanitized_dict(self) -> None:
        s = LLMSettings(api_key="sk-abc123")
        d = s.sanitized_dict()
        assert d["api_key"] == "***"

    def test_empty_api_key_not_masked(self) -> None:
        s = LLMSettings(api_key="")
        d = s.sanitized_dict()
        assert d["api_key"] == ""

    def test_frozen(self) -> None:
        s = LLMSettings(protocol="openai")
        with pytest.raises(FrozenInstanceError):
            s.protocol = "anthropic"  # type: ignore[misc]


# ── ObsidianSettings ─────────────────────────────────────────────────────────


class TestObsidianSettings:
    def test_defaults(self) -> None:
        s = ObsidianSettings()
        assert s.vault_path == ""
        assert s.subdir == "Inbox/evey2obs"
        assert s.attachment_subdir == "_attachments/evey2obs"

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EVEY2OBS_OBSIDIAN_VAULT", "/Users/test/vault")
        monkeypatch.setenv("EVEY2OBS_OBSIDIAN_SUBDIR", "Notes")
        monkeypatch.setenv(
            "EVEY2OBS_OBSIDIAN_ATTACHMENT_SUBDIR", "_attachments/notes"
        )

        app = AppSettings.from_env()
        assert app.obsidian.vault_path == "/Users/test/vault"
        assert app.obsidian.subdir == "Notes"
        assert app.obsidian.attachment_subdir == "_attachments/notes"

    def test_frozen(self) -> None:
        s = ObsidianSettings(vault_path="/tmp")
        with pytest.raises(FrozenInstanceError):
            s.vault_path = "/other"  # type: ignore[misc]


# ── AppSettings ──────────────────────────────────────────────────────────────


class TestAppSettings:
    def test_from_env_populates_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EVEY2OBS_LLM_PROTOCOL", "openai")
        monkeypatch.setenv("EVEY2OBS_LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("EVEY2OBS_LLM_API_KEY", "sk-test")
        monkeypatch.setenv("EVEY2OBS_LLM_MODEL", "gpt-4")
        monkeypatch.setenv("EVEY2OBS_OBSIDIAN_VAULT", "/tmp/vault")
        monkeypatch.setenv("EVEY2OBS_OBSIDIAN_SUBDIR", "Notes")
        monkeypatch.setenv("EVEY2OBS_WHISPER_MODEL", "medium")
        monkeypatch.setenv("EVEY2OBS_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("EVEY2OBS_TEMP_RETENTION_HOURS", "48")

        app = AppSettings.from_env()
        assert app.llm.protocol == "openai"
        assert app.llm.model == "gpt-4"
        assert app.obsidian.vault_path == "/tmp/vault"
        assert app.obsidian.subdir == "Notes"
        assert app.whisper_model == "medium"
        assert app.log_level == "DEBUG"
        assert app.temp_retention_hours == 48

    def test_from_env_missing_optional(self) -> None:
        app = AppSettings.from_env(environ={})
        assert app.proxy is None
        assert app.cookies_from_browser is None
        assert app.cookies_file is None

    def test_from_env_optional_set(self) -> None:
        app = AppSettings.from_env(
            environ={
                "EVEY2OBS_PROXY": "http://proxy:8080",
                "EVEY2OBS_COOKIES_BROWSER": "chrome",
                "EVEY2OBS_COOKIES_FILE": "/path/to/cookies.txt",
            }
        )
        assert app.proxy == "http://proxy:8080"
        assert app.cookies_from_browser == "chrome"
        assert app.cookies_file == "/path/to/cookies.txt"

    def test_whisper_model_default_is_small(self) -> None:
        app = AppSettings()
        assert app.whisper_model == "small"

    def test_temp_retention_hours_default_is_24(self) -> None:
        app = AppSettings()
        assert app.temp_retention_hours == 24

    def test_sanitized_dict_masks_api_key(self) -> None:
        app = AppSettings(llm=LLMSettings(api_key="sk-secret"))
        d = app.sanitized_dict()
        llm = d["llm"]
        assert isinstance(llm, dict)
        assert llm["api_key"] == "***"

    def test_sanitized_dict_masks_cookies(self) -> None:
        app = AppSettings(
            cookies_from_browser="chrome", cookies_file="/tmp/cookies.txt"
        )
        d = app.sanitized_dict()
        assert d["cookies_from_browser"] == "***"
        assert d["cookies_file"] == "***"

    def test_repr_masks_sensitive(self) -> None:
        app = AppSettings(llm=LLMSettings(api_key="sk-xyz"))
        r = repr(app)
        assert "sk-xyz" not in r

    def test_validate_raises_on_missing_vault(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        app = AppSettings(obsidian=ObsidianSettings(vault_path=str(nonexistent)))
        problems = app.validate()
        assert len(problems) == 1
        assert problems[0].code == ErrorCode.DISK_FULL

    def test_validate_raises_on_file_not_dir(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("not a dir")
        app = AppSettings(obsidian=ObsidianSettings(vault_path=str(f)))
        problems = app.validate()
        assert len(problems) == 1

    def test_validate_passes_on_writable_vault(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        app = AppSettings(obsidian=ObsidianSettings(vault_path=str(vault)))
        problems = app.validate()
        assert problems == []

    def test_validate_empty_vault_path_no_error(self) -> None:
        app = AppSettings()
        problems = app.validate()
        assert problems == []

    def test_validate_unwritable_vault(self, tmp_path: Path) -> None:
        vault = tmp_path / "readonly"
        vault.mkdir()

        # Monkey-patch touch to fail
        original_touch = vault.__class__.touch

        def _fail_touch(self, *args: object, **kwargs: object) -> None:  # noqa: ARG001
            raise OSError(errno.EACCES, "Permission denied")  # noqa: ARG005

        try:
            # Replace touch on the Path class
            Path.touch = _fail_touch  # type: ignore[method-assign]
            app = AppSettings(obsidian=ObsidianSettings(vault_path=str(vault)))
            problems = app.validate()
            assert len(problems) >= 1
        finally:
            Path.touch = original_touch  # type: ignore[method-assign]
