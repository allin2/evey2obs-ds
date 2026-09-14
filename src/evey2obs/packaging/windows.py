"""Windows portable bundle creator for evey2obs."""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WindowsPortableResult:
    bundle_dir: Path
    zip_path: Path
    launcher_path: Path


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {"__pycache__", ".pytest_cache", ".ruff_cache", ".git", ".DS_Store"}
    return {name for name in names if name in ignored or name.endswith((".pyc", ".pyo"))}


def _launcher_bat() -> str:
    return """@echo off
setlocal
set "DIR=%~dp0"
set "PYTHONPATH=%DIR%app\\src;%PYTHONPATH%"
python -m evey2obs gui %*
"""


class WindowsPortableBundleBuilder:
    """Creates a Windows portable directory and zip archive."""

    def __init__(
        self,
        project_root: Path,
        output_dir: Path,
        app_name: str = "evey2obs",
    ) -> None:
        self.project_root = project_root.resolve()
        self.output_dir = output_dir.expanduser().resolve()
        self.app_name = app_name

    def build(self) -> WindowsPortableResult:
        bundle_dir = self.output_dir / f"{self.app_name}-windows-portable"
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)
        bundle_dir.mkdir(parents=True)

        bundled_app = bundle_dir / "app"
        shutil.copytree(
            self.project_root / "src",
            bundled_app / "src",
            ignore=_copy_ignore,
        )
        if (self.project_root / "docs").exists():
            shutil.copytree(
                self.project_root / "docs",
                bundle_dir / "docs",
                ignore=_copy_ignore,
            )

        launcher = bundle_dir / f"{self.app_name}.bat"
        launcher.write_text(_launcher_bat(), encoding="utf-8")

        zip_path = self.output_dir / f"{self.app_name}-windows-portable.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in bundle_dir.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(self.output_dir))

        return WindowsPortableResult(bundle_dir, zip_path, launcher)
