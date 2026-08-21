# Demo · CodeX-like AI Agent

形如 CodeX 的**全平台桌面 AI Agent 应用**：拿到一个项目后，Agent 将任务委派给子 Agent，由 Agent 自身决定委派质量（推理强度），并通过可对外扩展的 KV Cache 层让用户特化 Agent 的能力。

> 当前进度：**阶段一（文档站）**。

## 技术栈

LangChain · LangGraph · MCP · KV Cache · uv

## 文档

完整文档见 [docs/](docs/index.md)，或本地启动：

```bash
uv sync --group docs
uv run mkdocs serve
```

浏览器打开 <http://127.0.0.1:8000>。

## 开发约定

- Python 环境统一用 [uv](https://docs.astral.sh/uv/) 管理，固定 Python 3.13（`.python-version`）。
- 提交与文档写作规范见 [贡献指南](docs/contributing.md)。
