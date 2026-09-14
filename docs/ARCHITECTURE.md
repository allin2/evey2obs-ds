# evey2obs 架构说明

## 目标

架构需同时满足三个目标：

1. 从零建立可测试、可替换、不依赖历史实现的核心能力。
2. 平台解析变化时，不影响总结、Obsidian 导出和 UI。
3. 后续 Android/iOS 客户端可复用同一任务协议和核心处理流程。

## 分层

```text
Desktop GUI / CLI / Future Mobile Client
                 |
        Application Services
       Task Queue + Pipeline
                 |
              Domain
   ContentDocument / Task / Result
                 |
   +-------------+--------------+
   |             |              |
Source        Processors      Exporters
Adapters      ASR / LLM       Obsidian
```

### 表现层

- 桌面 GUI：链接输入、批量队列、进度、配置与结果展示。
- CLI：为测试、自动化、诊断和高级用户提供稳定入口。
- 表现层不得直接调用 yt-dlp、ffmpeg、Whisper 或平台 HTTP 接口。

### 应用层

- `TaskService`：创建、取消、重试和查询任务。
- `TaskQueue`：管理单链接与批量任务，限制重型转写并发数。
- `ProcessingPipeline`：编排识别、提取、转写、总结、导出和清理。
- 应用层只依赖协议，不依赖某个平台实现。

### 领域层

建议的核心模型：

```text
SourceInput
  raw_text, urls, local_files

ContentDocument
  source_id, source_type, content_type
  source_url, canonical_url
  title, author, published_at, duration
  body, transcript_segments, images, metadata, warnings

SummaryResult
  one_line_summary, key_points, detailed_notes
  action_items, quotes, tags, model_metadata

Task
  id, status, stage, progress, error, timestamps

ExportResult
  note_path, attachment_paths, manifest_path
```

领域模型不得包含浏览器 Cookie、API Key 或临时媒体签名。

### 平台适配器

每个来源实现统一协议：

```text
can_handle(input) -> bool
resolve(input) -> ResolvedSource
extract_metadata(source) -> SourceMetadata
extract_text(source) -> ExtractedText | None
extract_media(source) -> TemporaryMedia | None
```

首版适配器：

- Bilibili
- YouTube
- Douyin
- Xiaohongshu
- WeChat Official Account
- Xiaoyuzhou
- Local file fallback

平台认证、参数、短链和异常映射由适配器自己管理。

### 处理器

- `SubtitleProcessor`：规范化官方字幕和时间戳。
- `ArticleProcessor`：将 HTML 清洗为 Markdown，保留列表、表格、引用和链接。
- `MediaProcessor`：ffmpeg 音频提取、切片和格式统一。
- `TranscriptionProcessor`：Whisper 模型管理、分段转写和缓存。
- `SummarizationProcessor`：协议无关的 LLM 调用与结构化输出验证。
- 首版只保存原文图片，不调用 OCR。

### 导出器

Obsidian 导出使用两阶段写入：

1. 将笔记和附件写入 Vault 中的临时名称。
2. 验证内容和附件完整后原子替换为最终文件。

只有导出结果确认成功后，清理器才能删除临时音视频。

## 任务状态机

```text
queued
  -> resolving
  -> extracting
  -> transcribing (optional)
  -> summarizing
  -> exporting
  -> cleaning
  -> succeeded

Any active stage -> failed | cancelled
```

任务阶段和错误码属于 UI、CLI 和移动端的稳定协议，不应直接暴露第三方工具日志。

## 生产级弹性和性能特性

### 1. 转写内容指纹缓存 (`TranscriptCache`)
- 依据音频内容 SHA256 哈希及 Whisper 模型名称计算唯一缓存指纹。
- 转写完成时持久化脱敏 JSON，媒体下载前若检测到命中则跳过下载与转写，耗时从分钟级降至毫秒级。
- 缓存不包含本地路径、URL 或用户凭据，支持 `--force-refresh` 绕过与 `cache-clear` 清理。

### 2. 待导出草稿箱 (`PendingExportsManager`)
- 当 Vault 路径不存在、权限不足或磁盘已满导致导出失败时，自动将中间态（抽取文本、图片、AI 摘要）保存为独立草稿文件。
- 用户可在修复 Vault 配置后通过 GUI「待导出草稿」或 CLI `draft retry` 单独重试导出，无需重新下载媒体、重跑 Whisper 或重调大模型。

### 3. 安全凭据与脱敏 (`Security`)
- 普通设置写入本地平台配置目录；API Key 优先采用 OS 系统密钥链 (`keyring`) 安全存储。
- 所有输出与日志经脱敏处理器，剔除 URL 中的追踪分析参数（spm_id, bvid, utm 等）并脱敏敏感 Authorization/Token。

### 4. Obsidian 深度链接与交互
- 笔记导出后自动推导 Vault 名称与相对路径，生成 `obsidian://open?vault=...&file=...` 协议深链。
- GUI 提供一键「在 Obsidian 中打开」，实现从转写工具到知识库的无缝交互。

### 5. 跨平台打包与分发 (`Packaging`)
- `preflight`: 环境自检，验证 Python 运行时、构建后端、CLI/GUI 入口、关键依赖、随包文档和 Tkinter。
- `macos`: 构建标准化 macOS `.app` 应用程序包。
- `windows`: 构建免安装便携版 Windows ZIP 包。

## 配置与密钥

- 普通设置：本地配置文件。
- API Key：操作系统密钥链或环境变量。
- Cookie：仅在平台需要时临时读取，必须经用户明确授权。
- 日志统一经过脱敏器，移除凭据、追踪参数和本机敏感路径。

## 测试分层

- 单元测试：输入解析、状态机、数据模型、笔记渲染和脱敏。
- 适配器合约测试：每个平台运行同一组基础契约。
- 夹具测试：使用脱敏后的页面和 API 响应，不依赖实时网络。
- 验收矩阵测试：覆盖 12 种真实用例矩阵与异常路径报告。
- 端到端测试：使用临时 Vault 验证批量队列、附件、笔记和清理行为。

