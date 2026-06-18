"""Pure Markdown renderer for ContentDocument + SummaryResult → Obsidian note.

No I/O, no side effects — a single ``render_note()`` function that produces
the exact PRD section 12.2 output structure.
"""

from __future__ import annotations

from datetime import UTC, datetime

from evey2obs.models import ContentDocument, SummaryResult


def _needs_yaml_quoting(value: str) -> bool:
    """Check whether a YAML value needs quoting."""
    lower = value.strip().lower()
    if lower in ("true", "false", "null", "yes", "no", "on", "off", ""):
        return True
    # Quote if it starts with a character that could be confused with YAML syntax
    _yaml_special_start = (
        "'", '"', "&", "*", "!", "|", ">", "%", "@", "`", "[", "]", "{", "}", ","
    )
    if value and value[0] in _yaml_special_start:
        return True
    # Quote if a colon followed by a space appears (looks like a mapping key)
    if ": " in value or ":\n" in value:
        return True
    if value and value[-1] == ":":
        return True
    # Quote if it contains a hash followed by space (looks like a comment)
    if "# " in value or value.startswith("#"):
        return True
    # Quote if it contains special YAML flow indicators at word boundaries
    if any(ch in value for ch in ('"', "\n")):
        return True
    return False


def _escape_yaml_string(value: str) -> str:
    """Quote a string value for use in YAML frontmatter if needed."""
    if _needs_yaml_quoting(value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _format_date(dt: datetime | None) -> str:
    """Format a datetime as YYYY-MM-DD or empty string."""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d")


def _format_datetime_iso(dt: datetime) -> str:
    """Format a datetime as ISO 8601 with local timezone offset."""
    local = dt.astimezone()
    return local.isoformat()


def _format_yaml_list(items: tuple[str, ...]) -> str:
    """Format a tuple of strings as a YAML inline list [a, b, c]."""
    quoted = [_escape_yaml_string(item) for item in items]
    return "[" + ", ".join(quoted) + "]"


def render_note(document: ContentDocument, summary: SummaryResult) -> str:
    """Render a complete Obsidian Markdown note with YAML frontmatter.

    Returns a string suitable for writing directly to a ``.md`` file.
    """
    tags = summary.tags if summary.tags else document.tags
    now = datetime.now(UTC)

    # ── YAML frontmatter ───────────────────────────────────────────────
    frontmatter_lines: list[str] = ["---"]
    frontmatter_lines.append(f"title: {_escape_yaml_string(document.title or 'Untitled')}")
    frontmatter_lines.append(f"source: {_escape_yaml_string(document.source_url)}")
    frontmatter_lines.append(f"platform: {document.source_type.value}")
    frontmatter_lines.append(f"content_type: {document.content_type.value}")
    frontmatter_lines.append(f"author: {_escape_yaml_string(document.author or 'Unknown')}")
    frontmatter_lines.append(
        f"extraction_method: {document.extraction_method.value}"
    )
    published = _format_date(document.published_at) or "Unknown"
    frontmatter_lines.append(f"published: {published}")
    frontmatter_lines.append(f"created: {_format_datetime_iso(now)}")
    frontmatter_lines.append(f"tags: {_format_yaml_list(tags)}")
    frontmatter_lines.append("---")
    frontmatter_lines.append("")

    # ── Body ──────────────────────────────────────────────────────────
    body_lines: list[str] = []

    # Title
    body_lines.append(f"# {document.title or 'Untitled'}")
    body_lines.append("")

    # One-line summary
    body_lines.append("## 一句话总结")
    body_lines.append("")
    body_lines.append(summary.one_line_summary or "(无)")
    body_lines.append("")

    # Key points
    body_lines.append("## 核心要点")
    body_lines.append("")
    if summary.key_points:
        for point in summary.key_points:
            body_lines.append(f"- {point}")
    else:
        body_lines.append("(无)")
    body_lines.append("")

    # Detailed notes
    body_lines.append("## 详细笔记")
    body_lines.append("")
    body_lines.append(summary.detailed_notes or "(无)")
    body_lines.append("")

    # Action items
    body_lines.append("## 行动项")
    body_lines.append("")
    if summary.action_items:
        for item in summary.action_items:
            body_lines.append(f"- [ ] {item}")
    else:
        body_lines.append("(无)")
    body_lines.append("")

    # Timeline / Quotes
    body_lines.append("## 时间轴 / 关键引用")
    body_lines.append("")
    if summary.quotes:
        for quote in summary.quotes:
            body_lines.append(f"> {quote}")
            body_lines.append("")
    else:
        body_lines.append("(无)")
        body_lines.append("")

    # Full text / transcript
    body_lines.append("## 原始正文 / 完整转写")
    body_lines.append("")
    body_lines.append(document.text or "(无)")
    body_lines.append("")

    # Original images
    body_lines.append("## 原文图片")
    body_lines.append("")
    if document.images:
        for img in document.images:
            if img.local_path:
                body_lines.append(f"![]({img.local_path})")
            else:
                caption = img.caption or "图片"
                body_lines.append(f"[{caption}]({img.url}) (未下载)")
    else:
        body_lines.append("(无)")
    body_lines.append("")

    # Source info
    body_lines.append("## 来源与处理说明")
    body_lines.append("")
    body_lines.append(f"- **平台**: {document.source_type.value}")
    body_lines.append(f"- **原始链接**: {document.source_url}")
    body_lines.append(f"- **提取方式**: {document.extraction_method.value}")
    body_lines.append(f"- **作者**: {document.author or 'Unknown'}")
    if document.published_at:
        body_lines.append(f"- **发布时间**: {_format_date(document.published_at)}")
    if document.warnings:
        body_lines.append(f"- **注意事项**: {', '.join(document.warnings)}")

    return "\n".join(frontmatter_lines) + "\n".join(body_lines)
