# evey2obs-ds 项目状态

## 当前阶段

**阶段 6 完成：桌面 GUI 已实现。313 测试通过，Ruff 零问题。**

## 已完成

- **阶段 0-5**：全部业务层（7 个平台适配器 + 处理管线 + 导出 + 清理）
- **阶段 6：桌面 GUI**
  - `gui/app.py`：tkinter 主窗口（输入区、任务队列、结果面板、菜单栏）
  - `gui/asyncio_bridge.py`：asyncio ↔ tkinter 线程桥接（后台 pipeline，前台 poll 事件）
  - `gui/constants.py`：中文标签/平台图标/错误消息/Whisper 模型大小
  - 首次配置向导（4 步：LLM 配置 + Obsidian Vault + Whisper + 完成）
  - 设置对话框（大模型 / Obsidian / 高级设置）
  - 实时任务进度（排队 → 识别 → 提取 → 转写 → 总结 → 导出 → 完成）
  - `evey2obs gui` CLI 命令
  - `ProcessingPipeline.get_result()` 结果存取
  - 15 项 GUI 相关测试（常量、桥接、URL 预览）
  - 首次配置和设置表单会校验并应用到当前运行实例
  - URL 提交统一去重，队列显示平台、阶段进度和失败详情
  - **零新依赖**（仅 Python 标准库 tkinter）

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
Tests: 313 passed
Ruff: 0 issues
Doctor: ffmpeg + yt-dlp available
```

## 后续方向

- macOS 可分发包（py2app）
- 真实网络端到端验收测试
- Windows 路径兼容完善
- 移动端验证
