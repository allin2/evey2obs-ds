---
name: build-from-prd
description: Automatically use this skill when the user says "按照PRD构建项目", "按照 PRD 构建项目", "根据PRD继续开发", or asks to continue implementing evey2obs-ds from its product requirements.
---

# Build evey2obs-ds From PRD

## Source of truth

Read these files before acting:

1. `CLAUDE.md`
2. `docs/PRODUCT_REQUIREMENTS.html`
3. `docs/ARCHITECTURE.md`
4. `docs/IMPLEMENTATION_PLAN.md`
5. `docs/PROJECT_STATUS.md`
6. `pyproject.toml`
7. Current project source and tests

Do not read, copy, import, compare with, or infer behavior from any previous project code.

## Execution

1. Inspect Git status and the current project only.
2. Determine the first incomplete implementation slice from `PROJECT_STATUS.md` and `IMPLEMENTATION_PLAN.md`.
3. Use the `implementation-planner` subagent for a read-only plan when the slice is substantial.
4. State the slice, file scope, acceptance criteria, and validation commands briefly.
5. Add or update focused tests first.
6. Implement the smallest complete solution that satisfies the PRD and architecture.
7. Run pytest, ruff, and relevant type/build/integration checks.
8. Use the `code-reviewer` subagent after implementation.
9. Fix confirmed findings and rerun validation.
10. Update `docs/PROJECT_STATUS.md` with verified facts only.
11. Report the completed behavior, validation, residual risks, and next slice.

Do not merely propose a plan. Continue through implementation and verification for the selected slice unless blocked by missing user credentials, unavailable external services, or a product decision not covered by the PRD.
