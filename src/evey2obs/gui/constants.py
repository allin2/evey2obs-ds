"""Display labels and constants for the GUI."""

from evey2obs.models import ErrorCode, SourceType, TaskStatus

# ── Stage labels (PRD section 10.3) ────────────────────────────────────────

STAGE_LABELS: dict[TaskStatus, str] = {
    TaskStatus.QUEUED: "排队中",
    TaskStatus.RESOLVING: "正在识别来源",
    TaskStatus.EXTRACTING: "正在解析/提取",
    TaskStatus.TRANSCRIBING: "正在转写",
    TaskStatus.SUMMARIZING: "正在生成总结",
    TaskStatus.EXPORTING: "正在导出到 Obsidian",
    TaskStatus.CLEANING: "正在清理",
    TaskStatus.SUCCEEDED: "处理完成",
    TaskStatus.FAILED: "处理失败",
    TaskStatus.CANCELLED: "已取消",
}

# ── Platform labels ────────────────────────────────────────────────────────

PLATFORM_LABELS: dict[SourceType, str] = {
    SourceType.BILIBILI: "B站",
    SourceType.YOUTUBE: "YouTube",
    SourceType.DOUYIN: "抖音",
    SourceType.XIAOHONGSHU: "小红书",
    SourceType.WECHAT_ARTICLE: "微信公众号",
    SourceType.XIAOYUZHOU: "小宇宙",
    SourceType.LOCAL_FILE: "本地文件",
}

PLATFORM_ICONS: dict[SourceType, str] = {
    SourceType.BILIBILI: "📺",
    SourceType.YOUTUBE: "▶️",
    SourceType.DOUYIN: "🎵",
    SourceType.XIAOHONGSHU: "📕",
    SourceType.WECHAT_ARTICLE: "📰",
    SourceType.XIAOYUZHOU: "🎙️",
    SourceType.LOCAL_FILE: "📁",
}

# ── Error messages ─────────────────────────────────────────────────────────

ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INPUT_NO_URL: "分享文案中没有链接，请重新复制分享口令",
    ErrorCode.SOURCE_UNSUPPORTED: "暂不支持此平台",
    ErrorCode.SHARE_TOKEN_MISSING: "请从小红书 App 重新复制分享链接",
    ErrorCode.SHARE_TOKEN_EXPIRED: "分享链接已过期，请重新复制",
    ErrorCode.AUTH_REQUIRED: "需要登录，可在高级设置中配置 Cookie",
    ErrorCode.CONTENT_UNAVAILABLE: "内容不可用（已删除/私密/付费）",
    ErrorCode.ARTICLE_CHALLENGE: "需要验证，请尝试在浏览器中打开后复制全文",
    ErrorCode.NO_SPEECH: "未检测到有效语音（纯音乐或无人声）",
    ErrorCode.ASR_LOW_CONFIDENCE: "转写质量较低（方言/噪声），建议使用更清晰的音频",
    ErrorCode.LLM_FAILED: "AI 总结失败，已保留原文",
    ErrorCode.DISK_FULL: "磁盘空间不足或路径不可写",
}

# ── Whisper model sizes (approximate, for download estimate) ──────────────

WHISPER_MODEL_SIZES: dict[str, str] = {
    "tiny": "~75 MB",
    "base": "~145 MB",
    "small": "~488 MB",
    "medium": "~1.5 GB",
    "large": "~2.9 GB",
}

# ── Colors ─────────────────────────────────────────────────────────────────

COLOR_SUCCESS = "#2e7d32"
COLOR_FAILED = "#c62828"
COLOR_ACTIVE = "#1565c0"
COLOR_QUEUED = "#6a6a6a"
COLOR_BG = "#f5f5f5"

# ── Summarization templates ───────────────────────────────────────────────

TEMPLATE_LABELS: dict[str, str] = {
    "general": "通用知识笔记",
    "course": "课程学习笔记",
    "meeting": "会议/访谈纪要",
    "short_video": "短视频快讯提炼",
    "article": "文章深度精读",
}
