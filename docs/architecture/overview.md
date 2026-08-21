# 总体架构

> 本章为**参考设计**：描述目标形态与职责边界，供后续实现阶段对齐。落地过程中如有调整，将回写到本页。

## 分层视图

```mermaid
flowchart TB
    subgraph Shell[桌面壳]
        UI[前端 UI]
    end

    subgraph Runtime[Python Agent 运行时]
        API[本地 API 管理层]
        Orchestrator[根 Agent / 编排器]
        Graph[LangGraph 委派图]
        SubA[子 Agent A]
        SubB[子 Agent B]
    end

    subgraph Infra[基础设施层]
        Cap[能力特化层]
        Cache[缓存层]
        MCPLayer[MCP 工具层]
        Store[(持久化存储)]
    end

    UI --> Orchestrator
    Orchestrator --> Graph
    Graph --> SubA
    Graph --> SubB
    Graph --> Cap
    SubA --> MCPLayer
    SubB --> MCPLayer
    Cap --> Cache
    Cap --> Store
    MCPLayer --> Ext[外部工具 / 数据源]
    Orchestrator --> API
    SubA --> API
    SubB --> API
    API -->|HTTPS| Remote[远程模型 API]
```

## 各层职责

### 桌面壳

- 承载前端 UI，负责跨平台分发（macOS / Windows / Linux）；
- 与本地 Python 运行时通过进程间通信（IPC / 本地端口）交互；
- 框架选型（Tauri / Electron）待定（见 [ADR](decisions.md)）。

### Python Agent 运行时

- **本地 API 管理层**：统一管理模型密钥与端点，构建模型客户端（[模型接入](model-access.md)）；
- **根 Agent（编排器）**：接收用户的项目与目标，负责顶层规划与任务拆解；
- **LangGraph 委派图**：把任务组织成树形结构，管理状态流转、检查点与恢复；
- **子 Agent**：承接具体子任务，可继续向下委派。

### 基础设施层

- **能力特化层**：对外暴露接口，注入上下文 / 工具 / 提示 / 检索策略（[能力特化层](capability-layer.md)）；
- **缓存层**：prompt / 结果复用，降低 token 成本与延迟（内部优化）；
- **MCP 工具层**：统一接入外部工具与数据源；
- **持久化存储**：任务状态、检查点与缓存落盘。

## 关键设计原则

1. **编排与能力分离**：委派结构由 LangGraph 负责，具体“能做什么、知道什么”由能力特化层与 MCP 注入。
2. **特化不侵入核心**：用户自定义能力通过能力特化层接口接入，核心编排逻辑保持稳定。
3. **密钥与模型解耦**：模型客户端由本地 API 管理层统一构建，密钥不进入编排状态。
4. **可观测与可恢复**：委派树上的每个节点都可追踪、可局部重试。

## 深入阅读

- [任务委派树](delegation-tree.md)
- [推理强度](reasoning-effort.md)
- [能力特化层](capability-layer.md)
- [模型接入与 API 管理](model-access.md)
- [MCP 集成](mcp.md)
- [关键决策 (ADR)](decisions.md)
