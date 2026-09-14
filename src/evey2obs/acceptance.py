from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evey2obs import __version__


@dataclass(frozen=True, slots=True)
class AcceptanceCase:
    id: str
    label: str
    description: str

    def covered_by(self, sample: dict[str, Any]) -> bool:
        return _CASE_MATCHERS[self.id](sample)


REQUIRED_ACCEPTANCE_CASES = (
    AcceptanceCase("bilibili_public_video", "B站公开视频", "1 个公开中文视频。"),
    AcceptanceCase(
        "youtube_with_subtitles",
        "YouTube 有字幕",
        "1 个可走官方字幕路径的视频。",
    ),
    AcceptanceCase(
        "youtube_without_subtitles",
        "YouTube 无字幕",
        "1 个可走 Whisper 路径的视频。",
    ),
    AcceptanceCase("douyin_spoken_share", "抖音口播", "1 条口播分享文案。"),
    AcceptanceCase(
        "xiaohongshu_app_share",
        "小红书有效分享",
        "1 条有效 App 分享短链。",
    ),
    AcceptanceCase(
        "xiaohongshu_missing_token",
        "小红书缺 token",
        "1 条无 token 裸链接，期望 SHARE_TOKEN_MISSING。",
    ),
    AcceptanceCase("wechat_text_article", "公众号纯文字", "1 篇公开纯文字文章。"),
    AcceptanceCase("wechat_article_with_images", "公众号含图", "1 篇公开含图文章。"),
    AcceptanceCase(
        "xiaoyuzhou_show_notes",
        "小宇宙有文稿",
        "1 集可走 show notes 或官方文稿路径。",
    ),
    AcceptanceCase(
        "xiaoyuzhou_audio_only",
        "小宇宙无文稿",
        "1 集需走音频 + Whisper 路径。",
    ),
    AcceptanceCase("local_audio_file", "本地音频", "1 个本地 MP3/M4A/WAV。"),
    AcceptanceCase("local_video_file", "本地视频", "1 个本地 MP4/MOV/MKV。"),
)


def real_samples_path(environ: dict[str, str] | None = None) -> Path | None:
    env = environ if environ is not None else os.environ
    value = env.get("EVEY2OBS_REAL_SAMPLES", "").strip()
    return Path(value).expanduser() if value else None


def load_real_sample_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    samples = payload.get("samples", [])
    if not isinstance(samples, list):
        raise ValueError("Real sample manifest must contain a samples list.")
    return payload


def acceptance_report(manifest: dict[str, Any]) -> dict[str, Any]:
    samples = [
        sample
        for sample in manifest.get("samples", [])
        if isinstance(sample, dict) and bool(sample.get("enabled", True))
    ]
    cases = []
    missing = []
    for case in REQUIRED_ACCEPTANCE_CASES:
        matched = [
            safe_sample_id(sample, index)
            for index, sample in enumerate(samples)
            if case.covered_by(sample)
        ]
        entry = {
            "id": case.id,
            "label": case.label,
            "description": case.description,
            "covered": bool(matched),
            "sample_ids": matched,
        }
        cases.append(entry)
        if not matched:
            missing.append(case.id)
    return {
        "app": "evey2obs",
        "app_version": __version__,
        "schema": "evey2obs.real_samples.acceptance.v1",
        "sample_count": len(samples),
        "required_case_count": len(REQUIRED_ACCEPTANCE_CASES),
        "covered_case_count": len(REQUIRED_ACCEPTANCE_CASES) - len(missing),
        "complete": not missing,
        "missing": missing,
        "cases": cases,
    }


def acceptance_report_from_path(path: Path) -> dict[str, Any]:
    return acceptance_report(load_real_sample_manifest(path))


def safe_sample_id(sample: dict[str, Any], index: int = 0) -> str:
    value = str(sample.get("id") or f"sample-{index + 1}")
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._")[:80]
    return cleaned or f"sample-{index + 1}"


def _is_success(sample: dict[str, Any], source_type: str) -> bool:
    return sample.get("source_type") == source_type and bool(sample.get("expect_success", True))


def _methods(sample: dict[str, Any]) -> set[str]:
    values = sample.get("expected_extraction_methods", [])
    return {str(value) for value in values if str(value).strip()}


def _min_attachments(sample: dict[str, Any]) -> int:
    try:
        return int(sample.get("min_attachments", 0))
    except (TypeError, ValueError):
        return 0


def _has_local_file(sample: dict[str, Any], suffixes: set[str]) -> bool:
    if sample.get("source_type") != "local_file" or not bool(
        sample.get("expect_success", True)
    ):
        return False
    values = sample.get("local_files", [])
    if not isinstance(values, list):
        return False
    return any(Path(str(value)).suffix.lower() in suffixes for value in values)


_CASE_MATCHERS = {
    "bilibili_public_video": lambda sample: _is_success(sample, "bilibili"),
    "youtube_with_subtitles": lambda sample: _is_success(sample, "youtube")
    and "official_subtitle" in _methods(sample),
    "youtube_without_subtitles": lambda sample: _is_success(sample, "youtube")
    and "whisper" in _methods(sample),
    "douyin_spoken_share": lambda sample: _is_success(sample, "douyin"),
    "xiaohongshu_app_share": lambda sample: _is_success(sample, "xiaohongshu"),
    "xiaohongshu_missing_token": lambda sample: sample.get("source_type") == "xiaohongshu"
    and not bool(sample.get("expect_success", True))
    and sample.get("expected_error") == "SHARE_TOKEN_MISSING",
    "wechat_text_article": lambda sample: _is_success(sample, "wechat")
    and _min_attachments(sample) == 0,
    "wechat_article_with_images": lambda sample: _is_success(sample, "wechat")
    and _min_attachments(sample) >= 1,
    "xiaoyuzhou_show_notes": lambda sample: _is_success(sample, "xiaoyuzhou")
    and "show_notes" in _methods(sample),
    "xiaoyuzhou_audio_only": lambda sample: _is_success(sample, "xiaoyuzhou")
    and "whisper" in _methods(sample),
    "local_audio_file": lambda sample: _has_local_file(sample, {".mp3", ".m4a", ".wav"}),
    "local_video_file": lambda sample: _has_local_file(sample, {".mp4", ".mov", ".mkv"}),
}
