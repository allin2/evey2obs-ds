按照 `docs/PRODUCT_REQUIREMENTS.html`、`docs/IMPLEMENTATION_PLAN.md` 和 `docs/PROJECT_STATUS.md`，
实现下一个范围最小且价值最高的未完成切片。

1. 检查 Git 状态与当前项目文件。
2. 调用 `implementation-planner` 只读子代理。
3. 先增加失败的测试，再写最小实现。
4. 运行 pytest、ruff 与必要的类型/构建检查。
5. 调用 `code-reviewer` 只读子代理，修复确认的问题并重新验证。
6. 更新 `docs/PROJECT_STATUS.md`。
7. 总结已完成行为、验证结果、剩余风险与下一切片。

不读取或对照任何旧项目代码。
不提交、推送或执行破坏性命令，除非用户明确要求。
