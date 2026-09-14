# evey2obs-ds 项目状态

## 当前阶段

**双项目融合与文件整理完成：已将原版成熟特性（转写缓存、草稿箱容灾、系统密钥链、Obsidian 深链、多场景总结模板、跨平台独立打包）与全部文档资产（新手指南、隐私说明、验收用例矩阵）全面整理并融入现代化基座。330 项测试全部通过，Ruff 零代码问题。**

## 已完成

- **阶段 0-5**：全部业务层（7 个平台适配器 + 处理管线 + 导出 + 清理）
- **阶段 6：桌面 GUI**（原生轻量 Tkinter + asyncio 线程桥接）
- **阶段 7：双项目优势融合与统一**
  - **转写本地指纹缓存 (`processors/transcript_cache.py`)**：基于内容哈希与 Whisper 模型缓存转写，二次处理秒级跳过下载与转写，支持 `--force-refresh` 强制重转。
  - **待导出草稿容灾箱 (`exporters/pending_exports.py`)**：Vault 异常或离线时安全暂存本地草稿，支持 GUI/CLI 一键“仅重试导出”，无需重耗 API 额度与转写耗时。
  - **系统级凭据安全 (`security.py`)**：通过系统密钥链（macOS Keychain / Windows Credential Manager）加密存储大模型 API Key，提供平滑降级与日志脱敏。
  - **Obsidian 协议深链 (`obsidian://open`)**：生成深链并在桌面端一键直达 Obsidian 对应笔记。
  - **多场景总结预设模板**：通用、课程学习、会议/访谈纪要、短视频快讯提炼、文章深度精读等定制化 Prompt 模板。
  - **跨平台独立打包分发 (`packaging/`)**：提供打包预检 `PackagePreflight`、macOS `.app` 构建器与 Windows 便携版生成器，支持 `evey2obs package-preflight`。
  - **真实用例验收覆盖评估 (`acceptance.py`)**：12 种真实用例矩阵覆盖评估，支持 `evey2obs acceptance-report`。
  - **文档资产完整归集**：整合 `GETTING_STARTED.html`（新手指南）、`PRIVACY.html`（隐私边界）、`PRODUCT_REQUIREMENTS.html`、样例配置与实机样例模板。
  - **CLI 运维扩展**：新增 `package-preflight`、`cache-clear`、`acceptance-report`、`draft {list|retry|remove}`。

## 全部平台适配器

| 平台 | 适配器 | 策略 |
|------|--------|------|
| B站 | BilibiliAdapter | 官方字幕 → Whisper |
| YouTube | YouTubeAdapter | 自动字幕 → Whisper |
| 抖音 | DouyinAdapter | 字幕 → 音频+Whisper |
| 小红书 | XiaohongshuAdapter | 字幕/INITIAL_STATE → Whisper |
| 公众号 | WeChatArticleAdapter | HTML→Markdown + 图片 |
| 小宇宙 | XiaoyuzhouAdapter | 文稿 → 音频+Whisper |
| 本地文件 | LocalFileAdapter | Whisper 直接转写 |

## 当前验证

```text
Python: 3.11.15
Tests: 330 passed
Ruff: 0 issues
Doctor: ffmpeg + yt-dlp available
Package Preflight: all 6 checks passed
Acceptance Matrix: 12/12 cases covered
```

## 后续方向

- macOS 可分发包（py2app / PyInstaller）
- 真实网络端到端验收测试
- Windows 路径兼容完善
- 移动端验证

