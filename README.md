# Demo · CodeX-like AI Agent

形如 CodeX 的**全平台桌面 AI Agent 应用**：拿到一个项目后，Agent 将任务委派给子 Agent，由 Agent 自身决定委派质量（推理强度），并通过可对外扩展的**能力特化层**让用户特化 Agent 的能力。

> 当前进度：**阶段一（文档站）+ 阶段二（Agent 运行时）+ 阶段三（桌面壳：选型已定，脚手架待建）**。

## 技术栈

LangChain Core · LangGraph · MCP · 能力特化层 · 本地 API 管理 · uv · Tauri · Nuxt(Vue3+TS)

## 桌面应用

桌面壳选型为 **Tauri 2 + Nuxt（Vue 3 + TS，SPA）**，Python Agent 运行时以 sidecar 进程打包分发（python-build-standalone + uv），进程间走 **stdio（NDJSON 中继）**。架构见 [docs/architecture/desktop.md](docs/architecture/desktop.md) 与 [ADR-007](docs/architecture/decisions.md)。

脚手架位于 [`apps/desktop/`](apps/desktop/)（当前为骨架）：

```bash
# 1) Python 运行时
uv sync

# 2) 前端 + 桌面壳（Rust 侧自动拉起 --stdio sidecar）
cd apps/desktop
pnpm install
pnpm tauri dev

# 也可单独跑前端（浏览器联调，直连 WS）
pnpm dev                                            # http://127.0.0.1:3000
uv run python -m demo_agent.server --port 8765      # 另一终端起 WS 服务
```

> 事件协议见 `demo_agent/server.py` 顶部注释；开发态前端可直连 WS，打包态走 Tauri stdio 中继。

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

强度分档对照实验（judge 打分，质量 vs token 成本，走真实模型）：

```bash
uv run python -m demo_agent.experiment
```

详见 [评估与校准](docs/architecture/eval.md)。

## 文档

完整文档见 [docs/](docs/index.md)，站点源码在 [`apps/docs/`](apps/docs/)（Vite + Vue 3 + naive-ui），并已通过 GitHub Actions 自动发布到 <https://haha-ha-cuo.github.io/AuroraAgent-demo/>。本地预览：

```bash
cd apps/docs
pnpm install
pnpm dev            # http://127.0.0.1:5173
```

## 开发约定

- Python 环境统一用 [uv](https://docs.astral.sh/uv/) 管理，固定 Python 3.13（`.python-version`）。
- 不引入 `langchain` 元包，直接用 `langchain-core` + `langgraph`（[ADR-003](docs/architecture/decisions.md)）。
- 桌面壳新增 Rust（Tauri core）与 Nuxt/Vue3+TS 技术线，前端依赖用 pnpm 管理（[ADR-007](docs/architecture/decisions.md)）。
- 提交与文档写作规范见 [贡献指南](docs/contributing.md)。
