# 贡献指南

## 仓库结构约定

```
.
├── docs/              # 文档站内容（Markdown，单一内容源）
├── apps/
│   ├── docs/          # 文档站（Vite + Vue 3 + naive-ui）
│   └── desktop/       # 桌面壳（Tauri 2 + Nuxt）
├── .github/workflows/ # CI（含文档站自动发布）
├── pyproject.toml     # 项目元数据与依赖分组（uv 管理）
├── .python-version    # 固定的 Python 版本
└── AGENTS.md          # 项目目标与构想（勿随意改动）
```

> 应用代码将在阶段二加入，届时本页补充其目录结构与规范。

## uv 约定

- 所有 Python 环境与依赖统一由 **uv** 管理，禁止裸 `pip install`；
- 依赖放入 `pyproject.toml` 的对应分组；前端依赖（文档站 / 桌面壳）统一用 pnpm 管理，锁文件分别落在 `apps/*/pnpm-lock.yaml`；
- 环境固定 Python 3.13，由根目录 `.python-version` 声明；
- 变更依赖后务必提交更新后的 `uv.lock`。

## 提交规范

建议使用 Conventional Commits 风格的提交信息，前缀包括：

- `docs:` 文档变更
- `feat:` 新功能
- `fix:` 缺陷修复
- `chore:` 构建 / 工具链 / 配置

示例：

```
docs: 新增能力特化层设计文档
```

## 文档写作约定

- **语言**：正文使用简体中文；专有名词（LangChain、LangGraph、MCP、能力特化层、缓存层）保持统一；
- **结构**：架构类章节以“参考设计”标注开头，落地后回写为实际行为；
- **图表**：优先使用 Mermaid，便于随代码演进维护；
- **链接**：站内链接用相对路径（如 `../architecture/overview.md`），文档站会自动改写为路由链接；
- **术语**：统一使用下表术语，避免混用。

| 术语 | 统一写法 |
| --- | --- |
| LangChain 核心抽象 | LangChain Core / `langchain-core` |
| LangGraph | LangGraph |
| MCP | MCP |
| 能力特化层 | 能力特化层（Capability / Specialization） |
| 缓存层 | 缓存层（Cache，内部优化） |
| 推理强度 | 推理强度（reasoning effort） |

> 依赖约定：不引入 `langchain` 元包，直接使用 `langchain-core` + `langgraph` + 集成包（见 [ADR-003](architecture/decisions.md#adr-003)）。

## 本地校验

提交前确保文档站与 Python 代码可干净构建：

```bash
# 文档站（构建产物在 apps/docs/dist/）
cd apps/docs && pnpm install && pnpm build

# Python（含最小 eval 回归）
uv sync && uv run python -m demo_agent.eval
```

构建出现任何错误都应先修复再提交。
