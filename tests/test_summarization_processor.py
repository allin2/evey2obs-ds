"""Tests for SummarizationProcessor — LLM API, chunking, output parsing."""

from __future__ import annotations

import json

from evey2obs.models import ContentDocument, ContentType, SourceType, SummaryResult
from evey2obs.processors.summarization import (
    SummarizationProcessor,
)
from evey2obs.protocols import Summarizer
from evey2obs.settings import LLMSettings


class TestProtocolCompliance:
    def test_implements_summarizer_protocol(self) -> None:
        proc = SummarizationProcessor(settings=LLMSettings())
        assert isinstance(proc, Summarizer)


class TestChunking:
    def test_short_text_no_chunking(self) -> None:
        result = SummarizationProcessor._chunk_text("Hello world", max_chars=8000)
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_long_text_is_chunked(self) -> None:
        text = "这是第一句。" * 2000  # well over 8000 chars
        result = SummarizationProcessor._chunk_text(text, max_chars=2000)
        assert len(result) > 1
        # All chunks should be <= max_chars (roughly)
        for chunk in result:
            assert len(chunk) <= 2200  # allow some slack for overlap

    def test_empty_text(self) -> None:
        result = SummarizationProcessor._chunk_text("")
        assert result == [""]


class TestOutputParsing:
    def test_valid_json(self) -> None:
        raw = json.dumps({
            "one_line_summary": "测试总结",
            "key_points": ["要点1", "要点2"],
            "detailed_notes": "详细笔记",
            "action_items": ["行动1"],
            "quotes": ["引用1"],
            "tags": ["标签1"],
        })
        result = SummarizationProcessor._parse_output(raw)
        assert result.one_line_summary == "测试总结"
        assert result.key_points == ("要点1", "要点2")
        assert result.detailed_notes == "详细笔记"
        assert result.action_items == ("行动1",)

    def test_markdown_wrapped_json(self) -> None:
        raw = "```json\n" + json.dumps({"one_line_summary": "test"}) + "\n```"
        result = SummarizationProcessor._parse_output(raw)
        assert result.one_line_summary == "test"

    def test_malformed_json_returns_fallback(self) -> None:
        result = SummarizationProcessor._parse_output("not json at all {broken")
        assert result.one_line_summary == "(AI 输出解析失败)"
        assert result.detailed_notes == "not json at all {broken"

    def test_empty_json_obj(self) -> None:
        result = SummarizationProcessor._parse_output("{}")
        assert result.one_line_summary == ""
        assert result.key_points == ()


class TestPromptBuilding:
    def test_user_prompt_includes_title(self) -> None:
        doc = ContentDocument(
            id="1",
            source_type=SourceType.YOUTUBE,
            content_type=ContentType.VIDEO,
            source_url="https://x.com",
            canonical_url="https://x.com",
            title="My Title",
            text="Hello",
        )
        prompt = SummarizationProcessor._build_user_prompt(doc, "Hello")
        assert "My Title" in prompt
        assert "youtube" in prompt

    def test_chunk_index_note(self) -> None:
        doc = ContentDocument(
            id="1",
            source_type=SourceType.YOUTUBE,
            content_type=ContentType.VIDEO,
            source_url="https://x.com",
            canonical_url="https://x.com",
            title="T",
            text="x",
        )
        prompt = SummarizationProcessor._build_user_prompt(doc, "x", chunk_index=2, total=5)
        assert "第 3/5" in prompt


class TestMergeResults:
    def test_merges_multiple_results(self) -> None:
        doc = ContentDocument(
            id="1",
            source_type=SourceType.YOUTUBE,
            content_type=ContentType.VIDEO,
            source_url="https://x.com",
            canonical_url="https://x.com",
            title="T",
            text="original",
        )
        r1 = SummaryResult(
            one_line_summary="Part 1",
            key_points=("A", "B"),
            action_items=("Do A",),
        )
        r2 = SummaryResult(
            one_line_summary="Part 2",
            key_points=("C",),
            action_items=("Do B",),
        )
        merged = SummarizationProcessor._merge_results([r1, r2], doc)
        assert "Part 1" in merged.one_line_summary
        assert "Part 2" in merged.one_line_summary
        assert "A" in merged.key_points
        assert "C" in merged.key_points
        assert "Do A" in merged.action_items
        assert "Do B" in merged.action_items

    def test_deduplicates_key_points(self) -> None:
        doc = ContentDocument(
            id="1",
            source_type=SourceType.YOUTUBE,
            content_type=ContentType.VIDEO,
            source_url="https://x.com",
            canonical_url="https://x.com",
            title="T",
            text="x",
        )
        r1 = SummaryResult(key_points=("A", "B"))
        r2 = SummaryResult(key_points=("B", "C"))
        merged = SummarizationProcessor._merge_results([r1, r2], doc)
        assert merged.key_points == ("A", "B", "C")
