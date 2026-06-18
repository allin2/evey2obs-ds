"""URL extraction and source identification from raw share text."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from evey2obs.models import SourceType

# ── Domain → SourceType mapping ─────────────────────────────────────────────

_DOMAIN_MAP: dict[str, SourceType] = {
    "bilibili.com": SourceType.BILIBILI,
    "www.bilibili.com": SourceType.BILIBILI,
    "b23.tv": SourceType.BILIBILI,
    "youtube.com": SourceType.YOUTUBE,
    "www.youtube.com": SourceType.YOUTUBE,
    "youtu.be": SourceType.YOUTUBE,
    "m.youtube.com": SourceType.YOUTUBE,
    "music.youtube.com": SourceType.YOUTUBE,
    "douyin.com": SourceType.DOUYIN,
    "www.douyin.com": SourceType.DOUYIN,
    "v.douyin.com": SourceType.DOUYIN,
    "xiaohongshu.com": SourceType.XIAOHONGSHU,
    "www.xiaohongshu.com": SourceType.XIAOHONGSHU,
    "xhslink.com": SourceType.XIAOHONGSHU,
    "mp.weixin.qq.com": SourceType.WECHAT_ARTICLE,
    "xiaoyuzhoufm.com": SourceType.XIAOYUZHOU,
    "www.xiaoyuzhoufm.com": SourceType.XIAOYUZHOU,
}

# ── URL extraction ──────────────────────────────────────────────────────────

# Matches URLs in plain text and markdown [text](url) syntax
_URL_RE = re.compile(
    r"""https?://[^\s<>"']+""",
    re.IGNORECASE,
)

# Extracts URL from markdown link syntax
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def extract_urls(raw_text: str) -> list[str]:
    """Extract and deduplicate HTTP(S) URLs from arbitrary text.

    Handles plain URLs, embedded URLs in prose, and markdown link syntax.
    Returns URLs in first-occurrence order.
    """
    if not raw_text.strip():
        return []

    seen: set[str] = set()
    result: list[str] = []

    # 1. Extract URLs from markdown links, then remove them from the text
    text_stripped = raw_text
    for match in _MD_LINK_RE.finditer(text_stripped):
        url = match.group(2).strip()
        if url.startswith(("http://", "https://")):
            if url not in seen:
                seen.add(url)
                result.append(url)

    # Remove markdown links from consideration (avoid double-counting)
    text_stripped = _MD_LINK_RE.sub(" ", text_stripped)

    # 2. Extract remaining plain URLs
    for match in _URL_RE.finditer(text_stripped):
        url = match.group(0).rstrip(".,;:!?)")
        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


# ── Source identification ───────────────────────────────────────────────────


def identify_source(url: str) -> SourceType | None:
    """Identify the platform for a given URL.

    Returns:
        The matching :class:`SourceType` or ``None`` for unsupported domains.
    """
    if not url:
        return None

    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
    except (ValueError, TypeError):
        return None

    hostname = parsed.hostname or ""
    hostname = hostname.lower()

    # Exact match first
    if hostname in _DOMAIN_MAP:
        return _DOMAIN_MAP[hostname]

    # Suffix match (e.g., "api.bilibili.com" → BILIBILI)
    for domain, source_type in _DOMAIN_MAP.items():
        if hostname == domain or hostname.endswith("." + domain):
            return source_type

    return None
