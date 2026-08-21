# Demo · CodeX-like AI Agent

形如 CodeX 的**全平台桌面 AI Agent 应用**：拿到一个项目后，Agent 会把任务委派给子 Agent，由 Agent 自身决定委派质量（推理强度），并通过可对外扩展的 KV Cache 层让用户特化 Agent 的能力。

> 当前处于**阶段一：文档站**。本仓库的架构章节为**参考设计**，待实现落地后逐步回填为实际行为文档。

## 核心特性

- **任务委派树**：根 Agent 将任务分解为树形结构，逐层委派给子 Agent（LangGraph 承载）。
- **自适应推理强度**：Agent 自行决定每次委派的质量档位，类比 CodeX 的 reasoning effort。
- **能力可特化**：在 KV Cache 层对外开放接口，用户可自定义特化 Agent 的上下文、工具与提示。
- **MCP 工具生态**：通过 MCP 接入外部工具与数据源。
- **全平台分发**：面向 macOS / Windows / Linux 的桌面应用形态。

## 快速入口

| 想做的事 | 前往 |
| --- | --- |
| 了解项目是什么 | [项目简介](overview/introduction.md) |
| 看看为什么这么设计 | [设计目标](overview/goals.md) |
| 弄清整体怎么拼 | [总体架构](architecture/overview.md) |
| 想本地跑起文档站 | [文档本地预览](getting-started/docs-preview.md) |
| 了解接下来做什么 | [路线图](roadmap.md) |

## 技术栈速览

- [LangChain](https://www.langchain.com/) —— Agent 与工具编排基础
- [LangGraph](https://www.langchain.com/langgraph) —— 有状态的任务委派图
- [MCP](https://modelcontextprotocol.io/) —— 模型上下文协议，工具/数据接入
- KV Cache —— 可特化的缓存与能力特化层
- uv —— Python 环境与依赖管理

详见[技术栈](overview/tech-stack.md)。
