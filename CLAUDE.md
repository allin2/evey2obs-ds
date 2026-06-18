# evey2obs-ds 项目指令

## 项目使命

evey2obs-ds 是一个从零设计和实现的本地优先工具。
它将 B站、YouTube、抖音、小红书、微信公众号和小宇宙分享链接转换为
包含完整原文、AI 摘要、关键观点、行动项、标签和来源元数据的 Obsidian 笔记。

本项目的开发组合是 <strong>Claude Code + DeepSeek V4 Pro</strong>：Claude Code 提供代码编辑、工具调用、任务编排与项目记忆，实际底层推理模型为 `deepseek-v4-pro`。
这不是“Claude 主模型 + DeepSeek 第二模型”的双模型编排，而是 Claude Code 运行在 DeepSeek V4 Pro 模型上。
项目级 `.claude/settings.json` 固定非敏感的网关与模型名，认证令牌仅保存在用户级 Claude Code 配置中。

## 每次会话的阅读顺序

在实现功能前，先阅读：

1. `README.md`
2. `docs/PRODUCT_REQUIREMENTS.html`
3. `docs/ARCHITECTURE.md`
4. `docs/IMPLEMENTATION_PLAN.md`
5. `docs/PROJECT_STATUS.md`
6. `docs/DEEPSEEK_SETUP.md`
7. `pyproject.toml`
8. 本次改动相关的源码和测试

开始前用不超过 10 行总结当前理解、本次边界与验证方式。

## PRD 构建触发器

当用户说“按照 PRD 构建项目”、“按照PRD构建项目”或同等含义的请求时：

1. 自动使用项目 Skill `build-from-prd`，不要要求用户补充一套开发指令。
2. 根据 `PROJECT_STATUS.md` 选择第一个未完成切片，不重复已验证工作。
3. 对实质性切片先使用 `implementation-planner`，然后由主会话实现和测试。
4. 实现后使用 `code-reviewer`，处理确认问题并重新验证。
5. 完成当前切片后更新项目状态，再向用户报告结果。

该句话是执行请求，不是只要求生成计划。

## 工作方式

- 先阅读现状，再修改代码；不根据文件名猜测实现。
- 一次只实现一个边界清晰、可独立测试的切片。
- 遵循现有 PRD 和架构；发现冲突时先说明，不静默修改产品边界。
- 不进行无关重构，不为未经确认的未来需求提前建造复杂抽象。
- 平台差异只存在于 `adapters/sources/`；GUI、CLI、总结与导出层不知道平台细节。
- 使用 Python 3.11+、显式类型、小函数、结构化错误和可测试的依赖注入。
- 处理外部 HTML/JSON 时使用解析器和结构化接口，不用脆弱的全局字符串替换。
- 不读取、复制、导入或对照任何旧项目代码；产品行为只以本项目 PRD 和新增测试为依据。
- 对较大的实现切片，先调用 `implementation-planner` 子代理输出只读方案，主会话实现后再调用 `code-reviewer` 子代理检查。

## 不可违反的产品规则

- 六个平台全部属于首版范围，实现顺序按从零实施计划执行。
- 官方字幕或公开正文优先，音频 + Whisper 兜底。
- GUI 必须支持单链接和批量队列，每项有独立进度、错误和重试。
- 导出必须包含原文/完整转写、原文图片、摘要、观点、行动项和完整来源。
- 只有在 Obsidian 笔记和附件完整落盘后，才能清理临时音视频。
- 首版保存图片但不做 OCR，不内建知识库问答。
- 不绕过付费、私密、DRM、验证码或账号访问控制。

## 安全与隐私

- 不读取或输出 `.env`、`.env.local`、Cookie 文件、系统密钥链和真实 Obsidian Vault 内容。
- 不在代码、测试、日志、文档或 Git 历史中写入 API Key、Token 和 Cookie。
- 平台分享 token 可仅在请求期间使用，不得写入文件名、普通日志和笔记。
- 测试使用脱敏夹具和临时 Vault，不得依赖个人账号。
- 不执行 `rm -rf`、`git reset --hard`、`git clean` 或其他破坏性命令。

## DeepSeek V4 Pro 工作要求

- 开始任务时检查当前模型是否为 `deepseek-v4-pro`；如果不是，在修改文件前明确说明。
- 不把 DeepSeek V4 Pro 的推理输出当作事实；结论必须用源码、测试或官方文档验证。
- 不仅依靠长篇分析；在执行前给出明确的文件范围、改动目标和验证命令。
- 输出代码后使用工具检查实际差异，不根据记忆声称已完成。
- DeepSeek V4 Pro 或 Anthropic 兼容端点不支持某项 Claude Code 能力时，明确说明限制，不伪造工具结果。

## 测试与交付

默认验证命令：

```bash
python -m pytest
python -m ruff check .
python -m evey2obs doctor
```

修改平台适配器时增加脱敏夹具测试；真实网络测试必须与默认测试隔离。
每轮完成时报告已改文件、用户行为变化、验证结果、剩余风险和下一个最小实现切片。

## 文档

- 较大的产品文档、说明与手册优先使用排版清晰的 HTML。
- 架构决策和实施记录使用 Markdown，便于审查差异。
- 用户可见行为、配置或输出契约改变时，同步更新 README 与需求文档。
