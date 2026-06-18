"""Protocol-agnostic LLM summarization via OpenAI-compatible and Anthropic APIs."""

from __future__ import annotations

import json
import re

import httpx

from evey2obs.errors import Evey2ObsError
from evey2obs.models import ContentDocument, SummaryResult
from evey2obs.protocols import Summarizer
from evey2obs.settings import LLMSettings

# ── Prompt template ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个专业的内容总结助手。请根据提供的文本，生成一份结构化的内容总结。

必须严格使用以下 JSON 格式返回（不要包含其他文字）：

{
  "one_line_summary": "一句话总结（不超过100字）",
  "key_points": ["要点1", "要点2", "要点3"],
  "detailed_notes": "详细笔记（可多段落）",
  "action_items": ["行动项1", "行动项2"],
  "quotes": ["值得引用的原文语句1", "值得引用的原文语句2"],
  "tags": ["标签1", "标签2"]
}

要求：
- one_line_summary 必须高度凝练，让读者一眼就知道内容主题。
- key_points 至少包含 3 条核心观点或发现。
- detailed_notes 应有实质性内容，不要仅重复标题。
- action_items 是可执行的待办事项或值得跟进的方向。
- quotes 从原文中摘录最有价值的关键句。
- tags 应有助于在 Obsidian 中检索和组织笔记。
- 如原文信息不足某字段，用空字符串或空数组表示。"""

SYSTEM_PROMPT_ARTICLE = """你是一个专业的内容总结助手。请根据提供的文章内容，生成一份结构化的总结。

必须严格使用以下 JSON 格式返回：

{
  "one_line_summary": "一句话总结文章主旨",
  "key_points": ["核心论点1", "核心论点2", "核心论点3"],
  "detailed_notes": "详细笔记（论点、论据、结论）",
  "action_items": ["值得深入的方向1", "值得深入的方向2"],
  "quotes": ["值得引用的原文语句1", "值得引用的原文语句2"],
  "tags": ["标签1", "标签2"]
}

要求：
- one_line_summary 凝练概括全文主旨。
- key_points 至少包含 3 条核心论点，区分作者观点与事实陈述。
- detailed_notes 应梳理文章的逻辑结构（引言-论证-结论）。
- action_items 是阅读后值得进一步研究或实践的方向。
- quotes 从原文中摘录关键句。
- tags 应有助于在 Obsidian 中按主题检索。"""

SYSTEM_PROMPT_AUDIO = """\
你是一个专业的内容总结助手。请根据提供的播客/音频转录内容，生成一份结构化的总结。

必须严格使用以下 JSON 格式返回：

{
  "one_line_summary": "一句话概括本期节目主题",
  "key_points": ["核心观点1", "核心观点2", "核心观点3"],
  "detailed_notes": "详细笔记（按话题或时间线组织）",
  "action_items": ["值得跟进的方向1", "值得跟进的方向2"],
  "quotes": ["嘉宾金句或关键引用1", "嘉宾金句或关键引用2"],
  "tags": ["标签1", "标签2"]
}

要求：
- one_line_summary 概括本期节目的核心主题。
- key_points 至少包含 3 条讨论要点或嘉宾观点。
- detailed_notes 按话题或时间线组织关键信息。
- action_items 是听完后值得进一步了解或实践的方向。
- quotes 摘录嘉宾的精彩发言或关键结论。
- tags 应有助于在 Obsidian 中按主题检索播客内容。"""

USER_PROMPT_TEMPLATE = """请总结以下内容：

标题：{title}
作者：{author}
平台：{platform}
内容类型：{content_type}

正文：
{text}"""

# ── Processor ───────────────────────────────────────────────────────────────


class SummarizationProcessor(Summarizer):
    """Calls an OpenAI-compatible or Anthropic-compatible API for summarization.

    Implements the :class:`~evey2obs.protocols.Summarizer` protocol.
    """

    def __init__(
        self,
        settings: LLMSettings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = http_client
        self._owns_client = http_client is None

    # ── Protocol ──────────────────────────────────────────────────────────

    async def summarize(self, document: ContentDocument) -> SummaryResult:
        """Generate structured summary from a content document.

        Long text is automatically chunked.  On failure the original
        text is preserved in *detailed_notes*.
        """
        if not document.text.strip():
            return SummaryResult(
                one_line_summary="(无文本内容可供总结)",
                detailed_notes=document.text,
                tags=document.tags,
            )

        client = self._ensure_client()

        try:
            chunks = self._chunk_text(document.text)
            results: list[SummaryResult] = []

            for i, chunk in enumerate(chunks):
                raw = await self._call_api(
                    client, document, chunk, chunk_index=i, total=len(chunks)
                )
                results.append(self._parse_output(raw))

            return self._merge_results(results, document)
        except Evey2ObsError:
            raise
        except Exception as exc:
            return SummaryResult(
                one_line_summary="(AI 总结失败)",
                detailed_notes=document.text,
                tags=document.tags,
                model_metadata=(
                    ("model", self._settings.model),
                    ("protocol", self._settings.protocol),
                    ("error", str(exc)[:200]),
                ),
            )

    def cancel(self) -> None:
        """Cancel is managed via httpx client lifecycle."""
        pass

    # ── API calls ─────────────────────────────────────────────────────────

    @staticmethod
    def _select_system_prompt(document: ContentDocument) -> str:
        """Select system prompt based on content type."""
        ct = document.content_type.value
        if ct == "article":
            return SYSTEM_PROMPT_ARTICLE
        elif ct == "audio":
            return SYSTEM_PROMPT_AUDIO
        return SYSTEM_PROMPT

    async def _call_api(
        self,
        client: httpx.AsyncClient,
        document: ContentDocument,
        chunk: str,
        chunk_index: int = 0,
        total: int = 1,
    ) -> str:
        if self._settings.protocol == "anthropic":
            return await self._call_anthropic(client, document, chunk, chunk_index, total)
        return await self._call_openai(client, document, chunk, chunk_index, total)

    async def _call_openai(
        self,
        client: httpx.AsyncClient,
        document: ContentDocument,
        chunk: str,
        chunk_index: int = 0,
        total: int = 1,
    ) -> str:
        user_prompt = self._build_user_prompt(document, chunk, chunk_index, total)
        system_prompt = self._select_system_prompt(document)
        payload = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
        }
        resp = await client.post(
            f"{self._settings.base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def _call_anthropic(
        self,
        client: httpx.AsyncClient,
        document: ContentDocument,
        chunk: str,
        chunk_index: int = 0,
        total: int = 1,
    ) -> str:
        user_prompt = self._build_user_prompt(document, chunk, chunk_index, total)
        system_prompt = self._select_system_prompt(document)
        payload = {
            "model": self._settings.model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "x-api-key": self._settings.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        resp = await client.post(
            f"{self._settings.base_url.rstrip('/')}/messages",
            json=payload,
            headers=headers,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # Find the text content block (DeepSeek uses thinking+text blocks)
        for block in data["content"]:
            if block.get("type") == "text":
                return block["text"]
        return data["content"][0].get("text", "")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
            self._owns_client = True
        return self._client

    @staticmethod
    def _build_user_prompt(
        document: ContentDocument,
        chunk: str,
        chunk_index: int = 0,
        total: int = 1,
    ) -> str:
        chunk_note = f"\n（第 {chunk_index + 1}/{total} 部分）" if total > 1 else ""
        return USER_PROMPT_TEMPLATE.format(
            title=document.title or "Unknown",
            author=document.author or "Unknown",
            platform=document.source_type.value,
            content_type=document.content_type.value,
            text=chunk,
        ) + chunk_note

    @staticmethod
    def _chunk_text(
        text: str, max_chars: int = 8000, overlap: int = 200
    ) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        sentences = re.split(r"(?<=[。！？.!?\n])\s*", text)
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for sentence in sentences:
            if current_len + len(sentence) > max_chars and current:
                chunks.append("".join(current))
                overlap_text = (
                    "".join(current[-2:]) if len(current) >= 2 else current[-1]
                )
                current = [overlap_text]
                current_len = len(overlap_text)
            current.append(sentence)
            current_len += len(sentence)

        if current:
            chunks.append("".join(current))

        return chunks or [text]

    @staticmethod
    def _parse_output(raw: str) -> SummaryResult:
        json_match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return SummaryResult(
                one_line_summary="(AI 输出解析失败)",
                detailed_notes=raw,
            )

        return SummaryResult(
            one_line_summary=str(data.get("one_line_summary", "")),
            key_points=tuple(data.get("key_points", [])),
            detailed_notes=str(data.get("detailed_notes", "")),
            action_items=tuple(data.get("action_items", [])),
            quotes=tuple(data.get("quotes", [])),
            tags=tuple(data.get("tags", [])),
        )

    @staticmethod
    def _merge_results(
        results: list[SummaryResult], document: ContentDocument
    ) -> SummaryResult:
        key_points: list[str] = []
        actions: list[str] = []
        quotes: list[str] = []
        tags: list[str] = []
        one_lines: list[str] = []
        notes_parts: list[str] = []

        for i, r in enumerate(results, 1):
            if r.one_line_summary:
                one_lines.append(r.one_line_summary)
            for kp in r.key_points:
                if kp not in key_points:
                    key_points.append(kp)
            for ai in r.action_items:
                if ai not in actions:
                    actions.append(ai)
            for q in r.quotes:
                if q not in quotes:
                    quotes.append(q)
            for t in r.tags:
                if t not in tags:
                    tags.append(t)
            if r.detailed_notes:
                notes_parts.append(f"## Part {i}\n{r.detailed_notes}")

        return SummaryResult(
            one_line_summary="; ".join(one_lines) if one_lines else "(无总结)",
            key_points=tuple(key_points),
            detailed_notes="\n\n".join(notes_parts) if notes_parts else document.text,
            action_items=tuple(actions),
            quotes=tuple(quotes),
            tags=tuple(tags),
        )
