"""Tests for packaging preflight and bundle builders."""

from pathlib import Path

from evey2obs.packaging import (
    MacOSAppBundleBuilder,
    PackagePreflight,
    WindowsPortableBundleBuilder,
)


def test_package_preflight_checks(tmp_path: Path):
    # Setup mock project
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "evey2obs"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "yt-dlp",
    "openai-whisper",
]

[project.scripts]
evey2obs = "evey2obs.cli:main"
""",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PRODUCT_REQUIREMENTS.html").write_text("PRD", encoding="utf-8")
    (docs / "ARCHITECTURE.md").write_text("Arch", encoding="utf-8")
    (docs / "IMPLEMENTATION_PLAN.md").write_text("Plan", encoding="utf-8")
    (docs / "PROJECT_STATUS.md").write_text("Status", encoding="utf-8")

    preflight = PackagePreflight(
        project_root=tmp_path,
        module_checker=lambda m: True,
        version_info=(3, 11, 0),
    )
    results = preflight.run_all()
    assert results["python"].ok is True
    assert results["build_backend"].ok is True
    assert results["scripts"].ok is True
    assert results["dependencies"].ok is True
    assert results["tkinter"].ok is True
    assert results["docs"].ok is True


def test_macos_app_bundle_builder(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    src = root / "src" / "evey2obs"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("__version__ = '0.1.0'", encoding="utf-8")
    (src / "cli.py").write_text("def main(): pass", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='evey2obs'", encoding="utf-8")

    out = tmp_path / "dist"
    builder = MacOSAppBundleBuilder(project_root=root, output_dir=out)
    result = builder.build()

    assert result.app_path.exists()
    assert result.executable_path.exists()
    assert result.info_plist_path.exists()
    assert (result.resources_path / "app" / "src" / "evey2obs" / "cli.py").exists()


def test_windows_portable_builder(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    src = root / "src" / "evey2obs"
    src.mkdir(parents=True)
    (src / "cli.py").write_text("def main(): pass", encoding="utf-8")

    out = tmp_path / "dist"
    builder = WindowsPortableBundleBuilder(project_root=root, output_dir=out)
    result = builder.build()

    assert result.bundle_dir.exists()
    assert result.zip_path.exists()
    assert result.launcher_path.exists()
    assert (result.bundle_dir / "app" / "src" / "evey2obs" / "cli.py").exists()
