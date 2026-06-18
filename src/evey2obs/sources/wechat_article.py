"""微信公众号 (WeChat Official Account) article adapter.

Extracts article title, author, body, and images from public
mp.weixin.qq.com article pages via direct HTTP.  Does NOT use
yt-dlp or require WeChat login credentials.
"""

from __future__ import annotations

import logging
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from evey2obs.errors import Evey2ObsError
from evey2obs.models import (
    ContentType,
    ErrorCode,
    ExtractedText,
    ExtractionMethod,
    ImageRef,
    ResolvedSource,
    SourceInput,
    SourceMetadata,
    SourceType,
    TemporaryMedia,
)
from evey2obs.protocols import SourceAdapter
from evey2obs.settings import AppSettings

logger = logging.getLogger(__name__)


class WeChatArticleAdapter(SourceAdapter):
    """Adapter for 微信公众号 (WeChat Official Account) articles."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._temp_dir = Path(tempfile.mkdtemp(prefix="evey2obs_wechat_"))
        self._http_client: httpx.AsyncClient | None = None

    # ── Protocol ──────────────────────────────────────────────────────────

    def can_handle(self, source_input: SourceInput) -> bool:
        from evey2obs.inputs import extract_urls
        all_urls = list(source_input.urls)
        if source_input.raw_text:
            all_urls.extend(extract_urls(source_input.raw_text))
        for url in all_urls:
            if "mp.weixin.qq.com" in url:
                return True
        return False

    async def resolve(self, source_input: SourceInput) -> ResolvedSource:
        url = self._extract_first_url(source_input)
        return ResolvedSource(
            source_type=SourceType.WECHAT_ARTICLE,
            content_type=ContentType.ARTICLE,
            canonical_url=self._sanitize_url(url),
            source_id=self._extract_source_id(url),
        )

    async def extract_metadata(self, source: ResolvedSource) -> SourceMetadata:
        html = await self._fetch_page(source.canonical_url)
        if not html:
            return SourceMetadata()
        soup = BeautifulSoup(html, "html.parser")
        return SourceMetadata(
            title=(
                self._select_one_text(soup, "#activity-name")
                or self._select_meta(soup, "og:title")
                or None
            ),
            author=(
                self._select_one_text(soup, "#js_name")
                or self._select_meta(soup, "og:article:author")
                or None
            ),
            published_at=self._parse_publish_time(soup),
        )

    async def extract_text(self, source: ResolvedSource) -> ExtractedText | None:
        html = await self._fetch_page(source.canonical_url)
        if not html:
            return None
        blocked = self._detect_blocked_state(html)
        if blocked:
            raise blocked
        soup = BeautifulSoup(html, "html.parser")
        body_el = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
        if not body_el:
            return ExtractedText(text="", extraction_method=ExtractionMethod.HTML)
        return ExtractedText(
            text=self._html_to_markdown(body_el),
            images=tuple(await self._extract_images(body_el)),
            extraction_method=ExtractionMethod.HTML,
        )

    async def extract_media(self, source: ResolvedSource) -> TemporaryMedia | None:
        return None

    # ── HTTP ──────────────────────────────────────────────────────────────

    async def _fetch_page(self, url: str) -> str | None:
        client = await self._get_client()
        try:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                timeout=20.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            logger.warning("Failed to fetch WeChat article: %s", exc)
            return None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client

    # ── Image extraction ──────────────────────────────────────────────────

    async def _extract_images(self, body: Tag) -> list[ImageRef]:
        images: list[ImageRef] = []
        for img_tag in body.find_all("img"):
            url = img_tag.get("data-src") or img_tag.get("src", "")
            if not url or not url.startswith("https://"):
                continue
            local_path = await self._download_image(url)
            images.append(ImageRef(
                url=url,
                local_path=str(local_path) if local_path else None,
                caption=img_tag.get("alt", ""),
            ))
        return images

    async def _download_image(self, url: str) -> Path | None:
        try:
            client = await self._get_client()
            resp = await client.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            suffix = ".jpg"
            ct = resp.headers.get("content-type", "")
            if "png" in ct:
                suffix = ".png"
            elif "webp" in ct:
                suffix = ".webp"
            dest = self._temp_dir / f"img_{hash(url) & 0xFFFFFF:06x}{suffix}"
            dest.write_bytes(resp.content)
            return dest
        except Exception:
            return None

    # ── URL helpers ───────────────────────────────────────────────────────

    def _extract_first_url(self, source_input: SourceInput) -> str:
        from evey2obs.inputs import extract_urls
        all_urls = list(source_input.urls)
        if source_input.raw_text:
            all_urls.extend(extract_urls(source_input.raw_text))
        for url in all_urls:
            if "mp.weixin.qq.com" in url:
                return url
        raise Evey2ObsError(
            code=ErrorCode.SOURCE_UNSUPPORTED,
            message="No WeChat article URL found",
        )

    @staticmethod
    def _sanitize_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    @staticmethod
    def _extract_source_id(url: str) -> str:
        m = re.search(r"/s/([a-zA-Z0-9_-]+)", url)
        if m:
            return m.group(1)
        parts = url.rstrip("/").split("/")
        return parts[-1] if parts else url

    # ── HTML parsing ──────────────────────────────────────────────────────

    @staticmethod
    def _select_one_text(soup: BeautifulSoup, selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else ""

    @staticmethod
    def _select_meta(soup: BeautifulSoup, prop: str) -> str:
        el = soup.select_one(f'meta[property="{prop}"]')
        return el.get("content", "") if el else ""

    @staticmethod
    def _parse_publish_time(soup: BeautifulSoup) -> datetime | None:
        el = soup.select_one("#publish_time")
        if el and el.get_text(strip=True):
            raw = el.get_text(strip=True)
            for fmt in ("%Y-%m-%d", "%Y年%m月%d日"):
                try:
                    return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue
        for script in soup.find_all("script"):
            text = script.string or ""
            m = re.search(r'var\s+ct\s*=\s*["\'](\d{10})["\']', text)
            if m:
                try:
                    return datetime.fromtimestamp(int(m.group(1)), tz=UTC)
                except (ValueError, OSError):
                    pass
        return None

    @staticmethod
    def _detect_blocked_state(html: str) -> Evey2ObsError | None:
        if any(kw in html for kw in ("环境异常", "请输入验证码", "验证身份")):
            return Evey2ObsError(
                code=ErrorCode.ARTICLE_CHALLENGE,
                message="CAPTCHA detected. 请尝试在浏览器中打开后复制全文",
                recoverable=True,
            )
        if any(kw in html for kw in ("该内容已被发布者删除", "内容已删除", "此内容因违规")):
            return Evey2ObsError(
                code=ErrorCode.CONTENT_UNAVAILABLE,
                message="Article has been deleted or made private",
                recoverable=False,
            )
        return None

    # ── HTML → Markdown ───────────────────────────────────────────────────

    @staticmethod
    def _html_to_markdown(body: Tag) -> str:
        lines: list[str] = []
        _walk_children(body, lines)
        return "\n\n".join(lines)


# ── Module-level Markdown conversion helpers ─────────────────────────────────


def _walk_children(el: Tag, lines: list[str]) -> None:
    for child in el.children:
        if isinstance(child, str):
            text = child.strip()
            if text:
                lines.append(text)
            continue
        if not isinstance(child, Tag):
            continue

        tag = child.name.lower()
        text = child.get_text(strip=True)
        if tag in ("p", "div", "section"):
            _walk_children(child, lines)
            if text and (not lines or lines[-1] != text):
                lines.append(text)
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            lines.append(f"{'#' * int(tag[1])} {text}")
        elif tag == "blockquote":
            for line in text.split("\n"):
                if line.strip():
                    lines.append(f"> {line.strip()}")
        elif tag in ("ul", "ol"):
            for li in child.find_all("li", recursive=False):
                prefix = "- " if tag == "ul" else "1. "
                li_text = li.get_text(strip=True)
                if li_text:
                    lines.append(f"{prefix}{li_text}")
        elif tag == "a":
            href = child.get("href", "")
            if href and text:
                lines.append(f"[{text}]({href})")
        elif tag in ("strong", "b"):
            lines.append(f"**{text}**")
        elif tag in ("em", "i"):
            lines.append(f"*{text}*")
        elif tag == "br":
            if lines and lines[-1]:
                lines[-1] += "\n"
        elif tag == "img":
            img_url = child.get("data-src") or child.get("src", "")
            if img_url:
                lines.append(f"![{child.get('alt', '')}]({img_url})")
        elif tag == "table":
            _table_to_markdown(child, lines)
        elif tag in ("pre", "code"):
            lines.append(f"```\n{text}\n```")
        else:
            _walk_children(child, lines)
            if text and text not in lines:
                lines.append(text)


def _table_to_markdown(table: Tag, lines: list[str]) -> None:
    rows = table.find_all("tr")
    if not rows:
        return
    for i, row in enumerate(rows):
        cells = row.find_all(["td", "th"])
        cell_texts = [c.get_text(strip=True) for c in cells]
        lines.append("| " + " | ".join(cell_texts) + " |")
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in cells) + " |")
