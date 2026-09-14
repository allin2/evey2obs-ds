# evey2obs

将 B站、YouTube、抖音、小红书、微信公众号和小宇宙的分享链接，一键转化为包含 AI 摘要、关键观点、行动项和来源元数据的 Obsidian 结构化笔记。

## 支持平台

| 平台 | 输入 | 提取策略 |
|------|------|----------|
| B站 | BV号、b23.tv 短链、分享文案 | 官方字幕 → Whisper 转写 |
| YouTube | 完整链接、youtu.be 短链 | 自动字幕 → Whisper 转写 |
| 抖音 | v.douyin.com 短链、分享口令 | 字幕优先 → 音频 + Whisper |
| 小红书 | xhslink.com 分享短链 | 视频/图文检测 → Whisper |
| 微信公众号 | mp.weixin.qq.com 文章链接 | HTML → Markdown + 图片 |
| 小宇宙 | xiaoyuzhoufm.com 单集链接 | 官方文稿 → 音频 + Whisper |
| 本地文件 | MP3、M4A、WAV、MP4、MOV | Whisper 直接转写 |

## 快速开始

### 1. 环境要求

- Python 3.11+
- ffmpeg（系统级安装：`brew install ffmpeg`）
- yt-dlp（`pip install yt-dlp`，已在依赖中）

### 2. 安装

```bash
cd /path/to/evey2obs-ds
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

### 3. 配置

设置环境变量（或在 GUI 首次配置向导中填写）：

```bash
# LLM 连接（必须）
export EVEY2OBS_LLM_PROTOCOL=anthropic          # 或 openai
export EVEY2OBS_LLM_BASE_URL=https://api.deepseek.com/anthropic
export EVEY2OBS_LLM_API_KEY=sk-xxxxx
export EVEY2OBS_LLM_MODEL=deepseek-v4-pro

# Obsidian Vault（必须）
export EVEY2OBS_OBSIDIAN_VAULT=/path/to/your/vault

# 可选
export EVEY2OBS_OBSIDIAN_SUBDIR=Inbox/evey2obs       # 默认
export EVEY2OBS_WHISPER_MODEL=small                    # tiny/base/small/medium/large
export EVEY2OBS_COOKIES_BROWSER=chrome                 # B站/YouTube 需要登录时
```

### 4. 启动

```bash
# 桌面 GUI（推荐）
evey2obs gui

# 或系统诊断
evey2obs doctor

# 测试 LLM 连接
evey2obs test-llm
```

### 5. 使用流程

1. 启动 GUI → 首次使用弹出配置向导
2. 粘贴链接或整段分享文案（支持多行批量粘贴）
3. 点击「识别链接」预览 → 「开始处理」
4. 任务队列显示实时进度
5. 完成后点击任务查看结果，可打开 Markdown、复制摘要

## 输出格式

每篇笔记按以下结构写入 Obsidian Vault：

```markdown
---
title: 视频标题
source: 原始链接
platform: bilibili
content_type: video
author: UP主名称
extraction_method: whisper
published: 2026-06-17
created: 2026-06-18T10:00:00+08:00
tags: [AI, 视频笔记]
---

# 标题
## 一句话总结
## 核心要点
## 详细笔记
## 行动项
## 时间轴 / 关键引用
## 原始正文 / 完整转写
## 原文图片
## 来源与处理说明
```

## 命令行

```bash
evey2obs doctor            # 系统诊断（Python、ffmpeg、yt-dlp、LLM、Vault）
evey2obs test-llm          # 测试 LLM 连接与总结能力
evey2obs gui               # 启动桌面 GUI（支持多任务队列、模板切换、草稿箱管理）
evey2obs package-preflight # 桌面打包前置验证（依赖、Tkinter、随包文档）
evey2obs cache-clear       # 清理音视频 Whisper 转写指纹缓存
evey2obs draft list        # 列出 Vault 写入失败保存的待导出草稿
evey2obs draft retry <id>  # 单独重试草稿导出（无需重新转写或重调大模型）
evey2obs draft remove <id> # 删除待导出草稿
```

## 项目结构

```
src/evey2obs/
├── models.py                   # 领域模型（ContentDocument、Task、ObsidianUri 等）
├── protocols.py                # 适配器/处理器/导出器协议
├── errors.py                   # 结构化错误（11 种核心错误码）
├── events.py                   # 进度事件、取消令牌
├── security.py                 # 系统密钥链凭据存储、URL 追踪清洗与敏感信息脱敏
├── settings.py                 # 类型化配置、环境变量、脱敏
├── inputs.py                   # URL 提取、平台识别、批量预检测
├── pipeline.py                 # 全流程编排（含缓存复用与草稿兜底机制）
├── cleaner.py                  # 临时音视频与图片文件清理
├── sources/                    # 7 个平台适配器
│   ├── base.py                 # yt-dlp 基类
│   ├── bilibili.py             # B站（公开 API，无需 Cookie）
│   ├── youtube.py              # YouTube
│   ├── douyin.py               # 抖音
│   ├── xiaohongshu.py          # 小红书
│   ├── wechat_article.py       # 微信公众号
│   ├── xiaoyuzhou.py           # 小宇宙播客
│   └── local_file.py           # 本地音频/视频文件
├── processors/                 # 核心处理器
│   ├── media.py                # ffmpeg 音频提取
│   ├── transcription.py        # Whisper 转写器
│   ├── transcript_cache.py     # 内容指纹缓存（免重复转写，支持强刷）
│   └── summarization.py        # 5 种场景模板 LLM 结构化总结（OpenAI/Anthropic）
├── exporters/                  # 导出器
│   ├── markdown.py             # Markdown 渲染
│   ├── obsidian.py             # Obsidian 原子写入与 URI 生成
│   └── pending_exports.py      # 待导出草稿持久化与免重试恢复
├── packaging/                  # 跨平台桌面打包模块
│   ├── preflight.py            # 打包前置环境与契约检查
│   ├── macos.py                # macOS .app 应用生成器
│   └── windows.py              # Windows 便携包生成器
└── gui/                        # 桌面 GUI（轻量级原生 Tkinter）
    ├── app.py                  # 主窗口、模板选择、草稿箱管理与深链跳转
    ├── asyncio_bridge.py       # 线程安全的异步事件桥接
    └── constants.py            # GUI 样式、主题与文案常量
```

## 文档指引

- [新手使用指南](docs/GETTING_STARTED.html) - 图文使用教程与常见问题
- [隐私与安全说明](docs/PRIVACY.html) - 数据流转、凭据存储与隐私边界
- [架构设计说明](docs/ARCHITECTURE.md) - 系统分层、协议与领域模型
- [项目进度追踪](docs/PROJECT_STATUS.md) - 阶段交付与双项目合并记录

## 开发与验证

```bash
pip install -e '.[dev,package]'
python -m pytest          # 326 个单元测试与集成测试全部通过
python -m ruff check .    # 0 错误 0 警告
python -m evey2obs package-preflight # 打包前置 6 项检查通过
```
