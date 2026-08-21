# Demo · CodeX-like AI Agent

形如 CodeX 的**全平台桌面 AI Agent 应用**：拿到一个项目后，Agent 将任务委派给子 Agent，由 Agent 自身决定委派质量（推理强度），并通过可对外扩展的**能力特化层**让用户特化 Agent 的能力。

> 当前进度：**阶段一（文档站）+ 阶段二的最小纵向切片 demo**。

## 技术栈

LangChain Core · LangGraph · MCP · 能力特化层 · 本地 API 管理 · uv

## 最小 demo

一个可运行的纵向切片：LangGraph 委派树 + 推理强度 + 能力特化层 + 本地 API 管理。无密钥可跑 mock 模式：

```bash
uv sync
uv run python -m demo_agent "列出项目文件结构，并阅读 README.md 总结项目定位"
```

配置密钥走真实模型（任意 OpenAI 兼容端点）：

```bash
cp .env.example .env   # 填入 AGENT_API_KEY / AGENT_BASE_URL / AGENT_MODEL
```

详见 [运行最小 demo](docs/getting-started/demo.md)。

## 评估

最小 eval 集（12 个 fixture，校准任务识别与推理强度，零 token 成本）：

```bash
uv run python -m demo_agent.eval
```

详见 [评估与校准](docs/architecture/eval.md)。

## 文档

完整文档见 [docs/](docs/index.md)，或本地启动：

```bash
uv sync --group docs
uv run mkdocs serve
```

浏览器打开 <http://127.0.0.1:8000>。

## 开发约定

- Python 环境统一用 [uv](https://docs.astral.sh/uv/) 管理，固定 Python 3.13（`.python-version`）。
- 不引入 `langchain` 元包，直接用 `langchain-core` + `langgraph`（[ADR-003](docs/architecture/decisions.md)）。
- 提交与文档写作规范见 [贡献指南](docs/contributing.md)。
