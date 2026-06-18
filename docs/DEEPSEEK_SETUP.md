# Claude Code + DeepSeek V4 Pro 配置

## 运行模式

本项目使用 Claude Code 作为开发工具，底层推理模型为 DeepSeek V4 Pro。
它是一个组合，而不是两个模型并行：

```text
用户 → Claude Code（工具、项目记忆、任务编排）
                  ↓
       DeepSeek V4 Pro（底层推理模型）
                  ↓
          读取、编辑、测试与审查项目
```

## 项目固定配置

`.claude/settings.json` 已包含可公开提交的非敏感值：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_MODEL": "deepseek-v4-pro",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-pro",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-pro",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro"
  }
}
```

因此，在该目录启动 Claude Code 时，主会话、默认模型别名和项目子代理均指向 `deepseek-v4-pro`。

## 用户级密钥

`ANTHROPIC_AUTH_TOKEN` 已在用户级 `~/.claude/settings.json` 中配置。
项目文件不保存、不复制、不打印该 Token。

新机器只需在用户级 Claude Code 配置或 CCSwitch 中设置：

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<your-token>"
  }
}
```

## 必要的项目文件

- `CLAUDE.md`：项目目标、约束、安全和完成定义。
- `.claude/settings.json`：固定 DeepSeek V4 Pro 模型并约束高风险工具。
- `.claude/agents/implementation-planner.md`：使用 DeepSeek V4 Pro 做只读实施计划。
- `.claude/agents/code-reviewer.md`：使用 DeepSeek V4 Pro 做只读代码审查。
- `.claude/commands/project-context.md`：建立项目上下文。
- `.claude/commands/implement-next.md`：执行下一个小步实现切片。
- `.claude/commands/build-from-prd.md`：显式触发 PRD 构建工作流。
- `.claude/skills/build-from-prd/SKILL.md`：识别“按照 PRD 构建项目”等自然语言请求。
- `docs/PRODUCT_REQUIREMENTS.html`：产品需求基线。
- `docs/ARCHITECTURE.md`：技术边界。
- `docs/IMPLEMENTATION_PLAN.md`：从零实施顺序与退出条件。
- `docs/PROJECT_STATUS.md`：当前已验证能力与下一切片。

## 启动与使用

```bash
cd /Users/qlyf/Developer/evey2obs-ds
claude doctor
claude
```

进入会话后先执行：

```text
/project-context
```

确认项目现状后，可直接输入：

```text
按照 PRD 构建项目
```

Claude Code 会自动使用 `build-from-prd` Skill，先调用只读实施规划代理，由主会话实现，然后再调用只读审查代理。三者底层都是 DeepSeek V4 Pro，但拥有不同的上下文与权限。

## 验证

Claude Code 启动后，使用 `/model` 检查当前模型。预期模型 ID：

```text
deepseek-v4-pro
```

再运行：

```bash
python -m pytest
python -m ruff check .
python -m evey2obs doctor
```

## 注意

- 不要把 `ANTHROPIC_AUTH_TOKEN` 写入 `.claude/settings.json`、`.env.example`、`CLAUDE.md` 或任何 Git 跟踪文件。
- DeepSeek V4 Pro 的模型推理必须由源码、测试和真实工具输出验证。
- 如果 `/model` 不是 `deepseek-v4-pro`，先检查项目级设置是否被本地或命令行配置覆盖。
- 项目运行时的 `EVEY2OBS_LLM_*` 是最终用户用于生成视频/文章总结的配置，与 Claude Code 开发模型配置分离。

参考：

- <https://code.claude.com/docs/en/settings>
- <https://code.claude.com/docs/en/model-config>
- <https://code.claude.com/docs/en/sub-agents>
