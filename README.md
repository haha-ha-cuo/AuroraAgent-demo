# Aurora Agent Demo

Aurora Agent Demo 是一套面向桌面的多 Agent 工作台。用户提交目标后，运行时会生成递归任务树，根据任务复杂度分配推理强度，并将执行过程、确认请求和最终报告实时同步到桌面端。

项目当前提供可完整演示的确定性 Mock 模式，无需配置模型密钥。

## 核心能力

- 项目为单位、对话为子结构的分组工作台
- 连续对话与多会话后台并行
- 同一会话单运行互斥、停止和失败重试
- 递归委派树、任务状态和流式输出
- 风险操作确认门
- 桌面端 Markdown/TXT 本地解析与模型上下文
- SQLite 会话、消息、运行和任务持久化
- stdio 与 WebSocket 共用 Runtime Protocol v1
- API Key 仅保存到系统钥匙串
- 系统、浅色和深色三档主题

## 技术栈

- 桌面端：Tauri 2、Rust
- 前端：Nuxt 4、Vue 3、TypeScript、Naive UI、Pinia
- Agent：Python 3.13、LangGraph、FastAPI
- 持久化：SQLite（WAL）
- 包管理：uv、pnpm、Cargo

## 项目结构

```text
AuroraAgent-demo/
├─ apps/desktop/                 # Nuxt + Tauri 桌面应用
│  ├─ app/components/            # 每个组件使用独立同名目录
│  ├─ app/pages/                 # Nuxt 页面路由
│  ├─ app/stores/                # 后端数据缓存与 UI 状态
│  └─ src-tauri/                 # Rust sidecar broker
├─ apps/docs/                    # 文档站（组件同样使用独立目录）
├─ demo_agent/
│  ├─ domain/                    # 项目、会话、运行、任务等领域模型
│  ├─ application/               # 应用服务、运行调度与配置解析
│  ├─ ports/                     # Model、MCP、KV、文档解析端口
│  ├─ adapters/                  # SQLite schema/仓储与 Mock Agent 适配器
│  └─ transport/                 # stdio / WebSocket 传输
├─ docs/architecture/            # 协议、桌面架构与路由文档
└─ tests/                        # Python runtime 测试
```

## 环境要求

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js 20 或更高版本
- pnpm 11
- Rust stable 与 Tauri 2 的系统依赖

更完整的环境说明见 [前置要求](docs/getting-started/prerequisites.md)。

## 启动桌面应用

```bash
# 仓库根目录
uv sync

cd apps/desktop
pnpm install
pnpm tauri dev
```

Rust broker 会通过 stdio 自动启动 Python runtime。默认使用 Mock Provider，不需要 API Key。

## 浏览器联调

`pnpm dev` 会在启动 Nuxt 时自动拉起 Python WebSocket runtime（端口 8765）：

```bash
cd apps/desktop
pnpm dev
```

访问 `http://127.0.0.1:3000`。如需改用自定义 WebSocket 地址，设置 `VITE_RUNTIME_WS` 即可跳过自动拉起。

## 页面路由

| 路径 | 用途 |
| --- | --- |
| `/` | 新建对话（默认项目）与空状态 |
| `/projects/:projectId` | 项目工作区：发起新对话并浏览项目内对话 |
| `/sessions/:sessionId` | 连续对话、任务执行与确认操作 |
| `/settings` | 主题、模型、运行时和本地数据管理 |

桌面静态构建使用 Hash Router，页面职责和后端接入说明见 [前端路由文档](docs/architecture/frontend-routes.md)。

## 测试与构建

```bash
# Python
uv run pytest

# 后端代码检查（ruff + 每文件 ≤350 行）
bash scripts/lint.sh

# 前端
cd apps/desktop
pnpm typecheck
pnpm test
pnpm generate

# Rust
cd src-tauri
cargo test --locked
cargo check --locked
```

## 打包 sidecar

桌面分发需要随应用携带自包含 Python runtime，避免依赖系统 Python：

```bash
bash scripts/build-sidecar.sh
```

脚本用 python-build-standalone + uv 生成 `apps/desktop/src-tauri/resources/sidecar/`（独立 CPython + 站点包），Tauri 打包时作为 `bundle.resources` 随应用分发；Rust broker 优先使用该运行时，缺失时才回退到 `uv run` 开发模式。

## 应用图标

桌面/移动端图标由前端 `public/logo.png` 生成，替换时执行：

```bash
cd apps/desktop
pnpm tauri icon public/logo.png
```

该命令会重写 `src-tauri/icons/` 下全部 PNG、ICNS、ICO、iOS 与 Android 图标。

## 数据与安全

- SQLite 是项目、会话、消息、运行、任务与非敏感配置的唯一事实源。
- 非敏感配置（Provider、Base URL、模型）以 SQLite 应用设置为准，`.env` 仅作为浏览器开发时的初始默认值。
- API Key 不进入 SQLite、Pinia、日志或 Agent 事件，只由 Rust 写入系统钥匙串（开发时经 `.env` 或进程注入）。
- `localStorage` 只保存主题、侧栏折叠等界面偏好和旧数据迁移标记。
- 附件只保存用户主动选择的本地路径与元数据；Markdown/TXT 正文按运行临时读取，不写入 SQLite 或日志，也不会自动上传到模型之外的服务。
- OpenAI-compatible Provider 已接入计划、任务执行和最终报告；MCP 与 KV cache 生产适配器仍为明确占位。
- 桌面端支持 UTF-8 的 `.md`、`.markdown`、`.txt`，最多 4 个文件、单文件 1 MiB、合计 2 MiB；只保存路径与元数据，不将正文写入 SQLite。
- 浏览器开发模式不能获得可信本地路径，因此不提供附件选择；开发 API Key 通过环境变量注入。
- SQLite schema v3 持久化项目、会话、消息、运行、任务、附件、审批和非敏感设置，并从 v1/v2 原地迁移。
- 选择 OpenAI Provider 后配置或网络错误会明确失败并输出脱敏诊断，不会静默回退 Mock。

## 架构文档

- [桌面架构](docs/architecture/desktop.md)
- [Runtime Protocol v1](docs/architecture/runtime-protocol.md)
- [前端路由与接入](docs/architecture/frontend-routes.md)
- [委派树设计](docs/architecture/delegation-tree.md)

贡献规范见 [docs/contributing.md](docs/contributing.md)。
