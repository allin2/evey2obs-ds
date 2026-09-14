from __future__ import annotations

import argparse
import sys

from evey2obs import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evey2obs",
        description="Multi-source content extraction and Obsidian export.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Check whether the project scaffold is available.")
    subparsers.add_parser("test-llm", help="Test the configured LLM connection.")
    subparsers.add_parser("gui", help="Launch the desktop GUI.")
    subparsers.add_parser("package-preflight", help="Run packaging readiness checks.")
    subparsers.add_parser("cache-clear", help="Clear Whisper transcript cache.")
    acc_p = subparsers.add_parser(
        "acceptance-report", help="Generate acceptance matrix coverage report."
    )
    acc_p.add_argument(
        "manifest", nargs="?", default=None, help="Optional path to real samples manifest JSON."
    )

    draft_p = subparsers.add_parser("draft", help="Manage pending export drafts.")
    draft_subs = draft_p.add_subparsers(dest="draft_action")
    draft_subs.add_parser("list", help="List all pending export drafts.")
    retry_p = draft_subs.add_parser("retry", help="Retry exporting a draft.")
    retry_p.add_argument("id", help="Draft ID to retry.")
    remove_p = draft_subs.add_parser("remove", help="Delete a draft.")
    remove_p.add_argument("id", help="Draft ID to remove.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return _cmd_doctor()
    if args.command == "test-llm":
        return _cmd_test_llm()
    if args.command == "gui":
        return _cmd_gui()
    if args.command == "package-preflight":
        return _cmd_package_preflight()
    if args.command == "cache-clear":
        return _cmd_cache_clear()
    if args.command == "acceptance-report":
        return _cmd_acceptance_report(args.manifest)
    if args.command == "draft":
        return _cmd_draft(args)

    parser.print_help()
    return 0


def _cmd_doctor() -> int:
    print(f"evey2obs {__version__}: project scaffold is ready")
    print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    # ffmpeg check
    from evey2obs.processors.media import MediaProcessor

    ffmpeg = MediaProcessor.check_ffmpeg()
    if ffmpeg.available:
        print(f"ffmpeg: available ({ffmpeg.path})")
        if ffmpeg.version:
            print(f"  {ffmpeg.version}")
    else:
        print("ffmpeg: NOT FOUND (install with: brew install ffmpeg)")

    # yt-dlp check
    import shutil
    ytdlp = shutil.which("yt-dlp")
    if ytdlp:
        print(f"yt-dlp: available ({ytdlp})")
    else:
        print("yt-dlp: NOT FOUND (install with: pip install yt-dlp)")

    return 0


def _cmd_gui() -> int:
    """Launch the tkinter desktop GUI."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("ERROR: tkinter is not available.")
        return 1

    from evey2obs.gui import launch_gui

    launch_gui()
    return 0


def _cmd_test_llm() -> int:
    """Test the configured LLM connection (FR-019)."""
    from evey2obs.settings import AppSettings

    settings = AppSettings.from_env()
    if not settings.llm.api_key:
        print("ERROR: No API key configured. Set EVEY2OBS_LLM_API_KEY.")
        return 1
    if not settings.llm.base_url:
        print("ERROR: No base URL configured. Set EVEY2OBS_LLM_BASE_URL.")
        return 1
    if not settings.llm.model:
        print("ERROR: No model configured. Set EVEY2OBS_LLM_MODEL.")
        return 1

    print("Testing LLM connection...")
    print(f"  Protocol: {settings.llm.protocol}")
    print(f"  Base URL: {settings.llm.base_url}")
    print(f"  Model: {settings.llm.model}")

    import asyncio

    import httpx

    async def _test() -> int:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.llm.protocol == "anthropic":
            headers["x-api-key"] = settings.llm.api_key
            headers["anthropic-version"] = "2023-06-01"
            payload = {
                "model": settings.llm.model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Say 'ok'"}],
            }
            endpoint = f"{settings.llm.base_url.rstrip('/')}/messages"
        else:
            headers["Authorization"] = f"Bearer {settings.llm.api_key}"
            payload = {
                "model": settings.llm.model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Say 'ok'"}],
            }
            endpoint = f"{settings.llm.base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                print("Connection successful ✓")
                return 0
            except httpx.HTTPStatusError as exc:
                print(f"HTTP error: {exc.response.status_code}")
                body = exc.response.text[:300]
                print(f"  {body}")
                return 1
            except Exception as exc:
                print(f"Connection failed: {exc}")
                return 1

    return asyncio.run(_test())


def _cmd_package_preflight() -> int:
    """Run preflight packaging validation checks."""
    from pathlib import Path

    from evey2obs.packaging.preflight import PackagePreflight

    root = Path(__file__).resolve().parent.parent.parent
    preflight = PackagePreflight(project_root=root)
    results = preflight.run_all()

    all_ok = True
    print("evey2obs 打包前置检查 (Package Preflight):")
    for name, res in results.items():
        icon = "✓" if res.ok else "✗"
        print(f"  [{icon}] {name}: {res.message}")
        if not res.ok:
            all_ok = False
            for k, v in res.details.items():
                print(f"      - {k}: {v}")

    return 0 if all_ok else 1


def _cmd_cache_clear() -> int:
    """Clear Whisper transcript cache."""
    from evey2obs.processors.transcript_cache import TranscriptionCache

    cache = TranscriptionCache()
    deleted = cache.clear()
    print(f"已清理 Whisper 转写缓存: 共删除 {deleted} 个条目")
    return 0


def _cmd_draft(args: argparse.Namespace) -> int:
    """Manage pending export drafts."""
    import asyncio

    from evey2obs.exporters.obsidian import ObsidianExporter
    from evey2obs.exporters.pending_exports import PendingExportsManager
    from evey2obs.settings import AppSettings

    mgr = PendingExportsManager()

    if args.draft_action == "list":
        drafts = mgr.list()
        if not drafts:
            print("待导出草稿箱为空。")
            return 0
        print(f"待导出草稿箱 ({len(drafts)} 条):")
        for d in drafts:
            print(f"  [{d.id[:8]}] {d.title} ({d.source_type}) - {d.created_at[:19]}")
            if d.error_message:
                print(f"      原因: {d.error_message}")
        return 0

    if args.draft_action == "retry":
        settings = AppSettings.from_env()
        if not settings.obsidian.vault_path:
            print("ERROR: 未配置 Obsidian Vault 路径 (EVEY2OBS_OBSIDIAN_VAULT)")
            return 1

        # Match prefix if partial id provided
        target_id = args.id
        all_drafts = mgr.list()
        for d in all_drafts:
            if d.id.startswith(target_id):
                target_id = d.id
                break

        exporter = ObsidianExporter(settings.obsidian)
        try:
            result = asyncio.run(mgr.retry_export(target_id, exporter))
            print(f"草稿导出成功: {result.note_path}")
            return 0
        except Exception as exc:
            print(f"导出失败: {exc}")
            return 1

    if args.draft_action == "remove":
        target_id = args.id
        all_drafts = mgr.list()
        for d in all_drafts:
            if d.id.startswith(target_id):
                target_id = d.id
                break
        if mgr.remove(target_id):
            print(f"已删除草稿: {target_id[:8]}")
            return 0
        print(f"未找到草稿: {target_id}")
        return 1

    print("请指定子命令: evey2obs draft {list|retry|remove}")
    return 1


def _cmd_acceptance_report(path_str: str | None = None) -> int:
    """Generate an acceptance matrix coverage report."""
    import json
    from pathlib import Path

    from evey2obs.acceptance import acceptance_report_from_path, real_samples_path

    path = Path(path_str) if path_str else real_samples_path()
    if path is None:
        default_sample = Path("docs/samples/real_samples.example.json")
        if default_sample.is_file():
            path = default_sample
    if path is None or not path.is_file():
        print(
            f"Error: Sample manifest not found at '{path}'. "
            "Set EVEY2OBS_REAL_SAMPLES or pass a file path."
        )
        return 1

    report = acceptance_report_from_path(path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("complete") else 1

