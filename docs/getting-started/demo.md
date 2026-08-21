# 运行最小 demo

demo 是一个**可运行的纵向切片**，用来验证核心架构假设，而非完整产品。它演示四件事：

1. **委派树**：根 Agent 规划 → 并行派发子 Agent → 汇总（LangGraph）。
2. **推理强度**：规划阶段按任务复杂度给出 low / medium / high 档位。
3. **能力特化层**：可插拔地注入上下文、工具、提示。
4. **本地 API 管理**：密钥本地管理、不泄露；无密钥回退 mock 模式。

## 安装依赖

```bash
uv sync
```

## 运行（mock 模式，无需密钥）

```bash
uv run python -m demo_agent "列出项目文件结构，并阅读 README.md 总结项目定位"
```

未配置 `AGENT_API_KEY` 时自动进入 mock 模式，用确定性输出跑通全流程。

## 运行（真实模型）

```bash
cp .env.example .env   # 填入密钥
uv run python -m demo_agent "列出项目文件结构，并阅读 README.md 总结项目定位"
```

`.env` 支持：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `AGENT_API_KEY` | API 密钥（回退 `OPENAI_API_KEY`） | 空 → mock |
| `AGENT_BASE_URL` | OpenAI 兼容端点 | `https://api.openai.com/v1` |
| `AGENT_MODEL` | 模型名 | `gpt-4o-mini` |

> 任意 OpenAI 兼容端点均可：DeepSeek `https://api.deepseek.com`、Ollama 网关 `http://localhost:11434/v1` 等。密钥只用于构造客户端，不写入日志与图状态。

## 输出示例

```text
模式: mock
模型: (未配置密钥，使用确定性 mock)

委派树（根 → 子 Agent）:
  ├─ task_list_files [low]    列出项目文件结构
  ├─ task_read_readme [medium] 阅读 README.md 并总结项目定位

汇总报告:
  1) [low] 列出项目文件结构 → ...
  2) [medium] 阅读 README.md 并总结项目定位 → ...
```

## 代码结构

```
demo_agent/
├── __main__.py      # CLI 入口
├── settings.py      # 本地 API 管理：.env 加载、模型客户端构建、密钥脱敏
├── capabilities.py  # 能力特化层：上下文 / 工具 / 提示 的可插拔注册
├── tools.py         # 只读工具（list_files / read_file），MCP 的接入占位
└── graph.py         # LangGraph 委派图：规划 → 派发 → 汇总
```

各模块职责与设计见[总体架构](../architecture/overview.md)与[关键决策 ADR](../architecture/decisions.md)。
