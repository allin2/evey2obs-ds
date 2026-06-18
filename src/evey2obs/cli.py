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
