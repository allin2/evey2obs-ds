"""Persist settings to ~/.config/evey2obs/settings.json.

Settings from the config file are loaded first, then overridden by
environment variables (env vars take priority).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from evey2obs.settings import AppSettings, LLMSettings, ObsidianSettings


def config_dir() -> Path:
    """Return the evey2obs config directory."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "evey2obs"


def config_path() -> Path:
    """Return path to settings.json."""
    return config_dir() / "settings.json"


def load_config() -> dict:
    """Load settings from config file, return empty dict if not found."""
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(settings: AppSettings) -> None:
    """Save current settings to config file (masks API key in file).

    The API key is stored as-is because the config file is at
    ~/.config/evey2obs/ with 0o700 permissions.
    """
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    # Restrict permissions on the directory
    d.chmod(0o700)

    data = {
        "llm": {
            "protocol": settings.llm.protocol,
            "base_url": settings.llm.base_url,
            "api_key": settings.llm.api_key,
            "model": settings.llm.model,
        },
        "obsidian": {
            "vault_path": settings.obsidian.vault_path,
            "subdir": settings.obsidian.subdir,
            "attachment_subdir": settings.obsidian.attachment_subdir,
        },
        "whisper_model": settings.whisper_model,
        "proxy": settings.proxy,
        "cookies_from_browser": settings.cookies_from_browser,
        "cookies_file": settings.cookies_file,
    }

    config_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_settings() -> AppSettings:
    """Load settings from config file, with env vars as overrides.

    Priority: env vars > config file > defaults
    """
    config = load_config()

    # Build LLM settings: config file as base, env vars override
    llm_cfg = config.get("llm", {})
    llm = LLMSettings(
        protocol=os.environ.get("EVEY2OBS_LLM_PROTOCOL", llm_cfg.get("protocol", "openai")),
        base_url=os.environ.get("EVEY2OBS_LLM_BASE_URL", llm_cfg.get("base_url", "")),
        api_key=os.environ.get("EVEY2OBS_LLM_API_KEY", llm_cfg.get("api_key", "")),
        model=os.environ.get("EVEY2OBS_LLM_MODEL", llm_cfg.get("model", "")),
    )

    obs_cfg = config.get("obsidian", {})
    obsidian = ObsidianSettings(
        vault_path=os.environ.get("EVEY2OBS_OBSIDIAN_VAULT", obs_cfg.get("vault_path", "")),
        subdir=os.environ.get("EVEY2OBS_OBSIDIAN_SUBDIR", obs_cfg.get("subdir", "Inbox/evey2obs")),
        attachment_subdir=os.environ.get(
            "EVEY2OBS_OBSIDIAN_ATTACHMENT_SUBDIR",
            obs_cfg.get("attachment_subdir", "_attachments/evey2obs"),
        ),
    )

    return AppSettings(
        llm=llm,
        obsidian=obsidian,
        whisper_model=os.environ.get(
            "EVEY2OBS_WHISPER_MODEL", config.get("whisper_model", "small")
        ),
        proxy=os.environ.get(
            "EVEY2OBS_PROXY", config.get("proxy", "") or None
        ) or None,
        cookies_from_browser=os.environ.get(
            "EVEY2OBS_COOKIES_BROWSER",
            config.get("cookies_from_browser", "") or None,
        ) or None,
        cookies_file=os.environ.get(
            "EVEY2OBS_COOKIES_FILE", config.get("cookies_file", "") or None
        ) or None,
    )
