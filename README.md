# Aurora Agent Demo

Aurora Agent Demo 是一套面向桌面的多 Agent 工作台。用户提交目标后，运行时会生成递归任务树，根据任务复杂度分配推理强度，并将执行过程、确认请求和最终报告实时同步到桌面端。

项目当前提供可完整演示的确定性 Mock 模式，无需配置模型密钥。

## 核心能力

- 连续对话与多会话后台并行
- 同一会话单运行互斥、停止和失败重试
- 递归委派树、任务状态和流式输出
- 风险操作确认门
- 本地文件引用与附件元数据
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
│  ├─ domain/                    # 会话、运行、任务等领域模型
│  ├─ application/               # 应用服务与运行调度
│  ├─ ports/                     # Model、MCP、KV、文档解析端口
│  ├─ adapters/                  # SQLite 与 Mock Agent 适配器
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

分别启动 Python WebSocket runtime 和 Nuxt：

```bash
# 终端一：仓库根目录
uv run python -m demo_agent --port 8765

# 终端二
cd apps/desktop
pnpm dev
```

访问 `http://127.0.0.1:3000`。如需修改 WebSocket 地址，可设置 `VITE_RUNTIME_WS`。

## 页面路由

| 路径 | 用途 |
| --- | --- |
| `/` | 新建会话与空状态 |
| `/sessions/:sessionId` | 连续对话、任务执行与确认操作 |
| `/settings` | 主题、模型、运行时和本地数据管理 |

桌面静态构建使用 Hash Router，页面职责和后端接入说明见 [前端路由文档](docs/architecture/frontend-routes.md)。

## 测试与构建

```bash
# Python
uv run pytest

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

## 数据与安全

- SQLite 是会话数据的唯一事实源。
- `localStorage` 只保存主题等界面偏好和旧数据迁移标记。
- API Key 不进入 SQLite、Pinia、日志或 Agent 事件，只由 Rust 写入系统钥匙串。
- 附件首版只保存用户主动选择的本地路径与元数据，不自动读取或上传内容。
- OpenAI、MCP、KV cache 和文档解析的生产适配器目前为明确占位；Mock 流程可完整运行。

## 架构文档

- [桌面架构](docs/architecture/desktop.md)
- [Runtime Protocol v1](docs/architecture/runtime-protocol.md)
- [前端路由与接入](docs/architecture/frontend-routes.md)
- [委派树设计](docs/architecture/delegation-tree.md)

贡献规范见 [docs/contributing.md](docs/contributing.md)。
