"""Tests for the pure Markdown renderer (render_note)."""

from __future__ import annotations

from datetime import UTC, datetime

from evey2obs.exporters.markdown import (
    _escape_yaml_string,
    _format_date,
    _format_yaml_list,
    render_note,
)
from evey2obs.models import (
    ContentDocument,
    ContentType,
    ExtractionMethod,
    ImageRef,
    SourceType,
    SummaryResult,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


class TestYamlEscaping:
    def test_simple_string(self) -> None:
        assert _escape_yaml_string("hello") == "hello"

    def test_null_string_quoted(self) -> None:
        assert _escape_yaml_string("null") == '"null"'

    def test_true_string_quoted(self) -> None:
        assert _escape_yaml_string("true") == '"true"'

    def test_colon_is_quoted(self) -> None:
        assert ":" in _escape_yaml_string("a: b")
        assert _escape_yaml_string("a: b").startswith('"')

    def test_hash_is_quoted(self) -> None:
        assert _escape_yaml_string("# tag").startswith('"')

    def test_empty_string_quoted(self) -> None:
        assert _escape_yaml_string("") == '""'


class TestFormatDate:
    def test_with_date(self) -> None:
        dt = datetime(2026, 6, 17, tzinfo=UTC)
        assert _format_date(dt) == "2026-06-17"

    def test_none(self) -> None:
        assert _format_date(None) == ""


class TestFormatYamlList:
    def test_single_item(self) -> None:
        assert _format_yaml_list(("a",)) == "[a]"

    def test_multiple_items(self) -> None:
        result = _format_yaml_list(("a", "b"))
        assert "a" in result
        assert "b" in result
        assert result.startswith("[")

    def test_empty(self) -> None:
        assert _format_yaml_list(()) == "[]"


# ── Frontmatter tests ────────────────────────────────────────────────────────


def _make_doc(title: str = "Test Title") -> ContentDocument:
    return ContentDocument(
        id="test-1",
        source_type=SourceType.YOUTUBE,
        content_type=ContentType.VIDEO,
        source_url="https://youtube.com/watch?v=abc",
        canonical_url="https://youtube.com/watch?v=abc",
        title=title,
        author="Test Author",
        published_at=datetime(2026, 6, 17, tzinfo=UTC),
        extraction_method=ExtractionMethod.SUBTITLE,
        text="Full transcript.",
        tags=("tag1", "tag2"),
    )


def _make_summary() -> SummaryResult:
    return SummaryResult(
        one_line_summary="One line summary.",
        key_points=("Point 1",),
        detailed_notes="Detailed.",
        action_items=("Action 1",),
        quotes=("Quote 1",),
        tags=("tag1", "tag2"),
    )


class TestRenderFrontmatter:
    def test_title_field(self) -> None:
        result = render_note(_make_doc(title="My Video"), _make_summary())
        assert "title: My Video" in result

    def test_source_field(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        # URL may be quoted due to colons
        assert "source:" in result
        assert "https://youtube.com/watch?v=abc" in result

    def test_platform_field(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "platform: youtube" in result

    def test_content_type_field(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "content_type: video" in result

    def test_author_field(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "author: Test Author" in result

    def test_extraction_method_field(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "extraction_method: subtitle" in result

    def test_published_field(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "published: 2026-06-17" in result

    def test_published_field_none(self) -> None:
        doc = _make_doc()
        doc = ContentDocument(
            id=doc.id,
            source_type=doc.source_type,
            content_type=doc.content_type,
            source_url=doc.source_url,
            canonical_url=doc.canonical_url,
            title=doc.title,
            published_at=None,
        )
        result = render_note(doc, _make_summary())
        assert "published: Unknown" in result

    def test_created_field_present(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "created: " in result
        # Should be ISO 8601 with timezone offset
        assert "T" in result

    def test_tags_field(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "tags: [tag1, tag2]" in result

    def test_frontmatter_delimited_by_dashes(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        lines = result.split("\n")
        assert lines[0] == "---"
        # Find closing --- before body starts
        closing_idx = next(i for i, line in enumerate(lines[1:], 1) if line == "---")
        assert closing_idx > 1


# ── Body tests ───────────────────────────────────────────────────────────────


class TestRenderBody:
    def test_h1_title(self) -> None:
        result = render_note(_make_doc(title="My Video"), _make_summary())
        assert "# My Video" in result

    def test_one_line_summary_section(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "## 一句话总结" in result
        assert "One line summary." in result

    def test_key_points_section(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "## 核心要点" in result
        assert "- Point 1" in result

    def test_detailed_notes_section(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "## 详细笔记" in result
        assert "Detailed." in result

    def test_action_items_section(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "## 行动项" in result
        assert "- [ ] Action 1" in result

    def test_quotes_section(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "## 时间轴 / 关键引用" in result
        assert "> Quote 1" in result

    def test_full_text_section(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "## 原始正文 / 完整转写" in result
        assert "Full transcript." in result

    def test_images_section(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "## 原文图片" in result

    def test_source_info_section(self) -> None:
        result = render_note(_make_doc(), _make_summary())
        assert "## 来源与处理说明" in result
        assert "youtube" in result

    def test_empty_summary_renders_gracefully(self) -> None:
        doc = _make_doc()
        empty = SummaryResult()
        result = render_note(doc, empty)
        assert "(无)" in result

    def test_image_with_local_path_renders_embed(self) -> None:
        doc = _make_doc()
        doc = ContentDocument(
            id=doc.id,
            source_type=doc.source_type,
            content_type=doc.content_type,
            source_url=doc.source_url,
            canonical_url=doc.canonical_url,
            title=doc.title,
            images=(
                ImageRef(
                    url="https://x.com/img.jpg",
                    local_path="_attachments/evey2obs/img.jpg",
                ),
            ),
        )
        result = render_note(doc, _make_summary())
        assert "![](_attachments/evey2obs/img.jpg)" in result

    def test_image_url_only_renders_link_with_notice(self) -> None:
        doc = _make_doc()
        doc = ContentDocument(
            id=doc.id,
            source_type=doc.source_type,
            content_type=doc.content_type,
            source_url=doc.source_url,
            canonical_url=doc.canonical_url,
            title=doc.title,
            images=(ImageRef(url="https://x.com/img.jpg", caption="Photo"),),
        )
        result = render_note(doc, _make_summary())
        assert "[Photo](https://x.com/img.jpg) (未下载)" in result

    def test_warnings_in_source_info(self) -> None:
        doc = _make_doc()
        doc = ContentDocument(
            id=doc.id,
            source_type=doc.source_type,
            content_type=doc.content_type,
            source_url=doc.source_url,
            canonical_url=doc.canonical_url,
            title=doc.title,
            warnings=("low confidence", "background noise"),
        )
        result = render_note(doc, _make_summary())
        assert "**注意事项**" in result
        assert "low confidence" in result
        assert "background noise" in result

    def test_title_with_colon_is_escaped(self) -> None:
        result = render_note(_make_doc(title="Title: Subtitle"), _make_summary())
        assert "Title: Subtitle" in result
        # The title with colon should be quoted in YAML
        assert '"Title: Subtitle"' in result or 'title: "Title: Subtitle"' in result
