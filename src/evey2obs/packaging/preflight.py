"""Preflight validation to ensure project is ready for binary packaging and distribution."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PackageCheckResult:
    ok: bool
    message: str
    details: dict[str, str] = field(default_factory=dict)


ModuleChecker = Callable[[str], bool]


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


class PackagePreflight:
    """Preflight check runner for evey2obs packaging."""

    def __init__(
        self,
        project_root: Path,
        module_checker: ModuleChecker | None = None,
        version_info: tuple[int, int, int] | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.module_checker = module_checker or _module_available
        self.version_info = version_info or (
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
        )

    def run_all(self) -> dict[str, PackageCheckResult]:
        pyproject = self._pyproject()
        return {
            "python": self.check_python(pyproject),
            "build_backend": self.check_build_backend(pyproject),
            "scripts": self.check_scripts(pyproject),
            "dependencies": self.check_dependencies(pyproject),
            "tkinter": self.check_tkinter(),
            "docs": self.check_docs(),
        }

    def check_python(self, pyproject: dict[str, Any] | None = None) -> PackageCheckResult:
        pyproject = pyproject or self._pyproject()
        requires = str(pyproject.get("project", {}).get("requires-python", ""))
        if self.version_info < (3, 11, 0):
            return PackageCheckResult(
                False,
                "Python 版本低于 3.11，不能作为首版打包运行时。",
                {"current": ".".join(str(part) for part in self.version_info)},
            )
        if ">=3.11" not in requires:
            return PackageCheckResult(
                False,
                "pyproject.toml 未声明 Python 3.11+ 运行要求。",
                {"requires_python": requires},
            )
        return PackageCheckResult(True, "Python 运行时要求可用于打包。", {"requires": requires})

    def check_build_backend(
        self, pyproject: dict[str, Any] | None = None
    ) -> PackageCheckResult:
        pyproject = pyproject or self._pyproject()
        backend = str(pyproject.get("build-system", {}).get("build-backend", ""))
        requirements = [
            str(value) for value in pyproject.get("build-system", {}).get("requires", [])
        ]
        if backend != "setuptools.build_meta" or not requirements:
            return PackageCheckResult(
                False,
                "构建后端未配置为可打包的 setuptools build backend。",
                {"backend": backend},
            )
        return PackageCheckResult(True, "构建后端已配置。", {"backend": backend})

    def check_scripts(self, pyproject: dict[str, Any] | None = None) -> PackageCheckResult:
        pyproject = pyproject or self._pyproject()
        scripts = pyproject.get("project", {}).get("scripts", {})
        expected = {"evey2obs"}
        missing = sorted(expected - set(scripts))
        if missing:
            return PackageCheckResult(
                False,
                "缺少打包后需要暴露的命令入口。",
                {"missing": ", ".join(missing)},
            )
        return PackageCheckResult(True, "CLI 与 GUI 入口已正确配置。", {"count": str(len(scripts))})

    def check_dependencies(
        self, pyproject: dict[str, Any] | None = None
    ) -> PackageCheckResult:
        pyproject = pyproject or self._pyproject()
        dependencies = [
            str(value) for value in pyproject.get("project", {}).get("dependencies", [])
        ]
        missing: list[str] = []
        if not any("yt-dlp" in value for value in dependencies):
            missing.append("yt-dlp")
        if not any("whisper" in value for value in dependencies):
            missing.append("openai-whisper")
        if missing:
            return PackageCheckResult(
                False,
                "打包依赖声明不完整。",
                {"missing": ", ".join(missing)},
            )
        return PackageCheckResult(True, "关键运行依赖已声明。", {"count": str(len(dependencies))})

    def check_tkinter(self) -> PackageCheckResult:
        if not self.module_checker("tkinter"):
            return PackageCheckResult(
                False,
                "当前 Python 运行时缺少 Tkinter，GUI 打包后无法启动。",
                {"next_action": "请使用带 Tk 支持的 Python，或在打包环境安装 Tcl/Tk。"},
            )
        return PackageCheckResult(True, "Tkinter 可用于桌面 GUI。")

    def check_docs(self) -> PackageCheckResult:
        required = (
            "README.md",
            "docs/PRODUCT_REQUIREMENTS.html",
            "docs/ARCHITECTURE.md",
            "docs/IMPLEMENTATION_PLAN.md",
            "docs/PROJECT_STATUS.md",
        )
        missing = [path for path in required if not (self.project_root / path).is_file()]
        if missing:
            return PackageCheckResult(
                False,
                "缺少打包随附的用户或工程文档。",
                {"missing": ", ".join(missing)},
            )
        return PackageCheckResult(True, "打包随附文档齐全。", {"count": str(len(required))})

    def _pyproject(self) -> dict[str, Any]:
        return tomllib.loads((self.project_root / "pyproject.toml").read_text(encoding="utf-8"))
