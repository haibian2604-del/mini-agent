# 001: README 的 Setup 和 Usage 章节是 TBD

`README.md` 的 Setup 和 Usage 两节只有 "TBD" 占位符，新用户无法照着上手。

## 要求

- Setup：克隆、`uv sync`、`.env` 需要哪些变量（参考 `src/mini_agent/config/default.yaml` 顶部注释）
- Usage：`mini-agent run/inspect` 的基本用法和 `--env docker` 示例
- 语言与现有 README 保持一致（英文）

## 验收标准

一个没参与过项目的人，只看 README 能在 5 分钟内跑通一次 `mini-agent run "echo hello"`（local 模式）。

## Status

Done (d46bd91): README had Setup/Usage since step 17; added Quickstart section covering the real 5-min blocker (default yaml model points at a custom endpoint — documented `--model` / yaml override).
