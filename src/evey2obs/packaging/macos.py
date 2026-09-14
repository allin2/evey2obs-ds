"""macOS .app bundle generator for evey2obs desktop application."""

from __future__ import annotations

import plistlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from evey2obs import __version__


@dataclass(frozen=True, slots=True)
class MacOSAppBundleResult:
    app_path: Path
    executable_path: Path
    info_plist_path: Path
    resources_path: Path


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {"__pycache__", ".pytest_cache", ".ruff_cache", ".git", ".DS_Store"}
    return {name for name in names if name in ignored or name.endswith((".pyc", ".pyo"))}


def _info_plist(app_name: str) -> dict[str, str | bool]:
    return {
        "CFBundleDevelopmentRegion": "zh_CN",
        "CFBundleDisplayName": app_name,
        "CFBundleExecutable": app_name,
        "CFBundleIdentifier": f"com.qlyf.{app_name}",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": app_name,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    }


def _launcher_script(app_name: str) -> str:
    return """#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTENTS_DIR="$(cd "${DIR}/.." && pwd)"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"

export PYTHONPATH="${RESOURCES_DIR}/app/src:${PYTHONPATH:-}"
exec python3 -m evey2obs gui "$@"
"""


class MacOSAppBundleBuilder:
    """Builds standard macOS .app bundle directory structure."""

    def __init__(
        self,
        project_root: Path,
        output_dir: Path,
        app_name: str = "evey2obs",
    ) -> None:
        self.project_root = project_root.resolve()
        self.output_dir = output_dir.expanduser().resolve()
        self.app_name = app_name

    def build(self) -> MacOSAppBundleResult:
        app_path = self.output_dir / f"{self.app_name}.app"
        contents = app_path / "Contents"
        macos = contents / "MacOS"
        resources = contents / "Resources"
        bundled_app = resources / "app"

        if app_path.exists():
            shutil.rmtree(app_path)
        macos.mkdir(parents=True)
        resources.mkdir(parents=True)

        shutil.copytree(
            self.project_root / "src",
            bundled_app / "src",
            ignore=_copy_ignore,
        )
        if (self.project_root / "docs").exists():
            shutil.copytree(
                self.project_root / "docs",
                resources / "docs",
                ignore=_copy_ignore,
            )

        info_plist = contents / "Info.plist"
        executable = macos / self.app_name
        info_plist.write_bytes(plistlib.dumps(_info_plist(self.app_name)))
        executable.write_text(_launcher_script(self.app_name), encoding="utf-8")
        executable.chmod(executable.stat().st_mode | 0o111)

        return MacOSAppBundleResult(app_path, executable, info_plist, resources)
