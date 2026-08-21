"""LangGraph 委派图：规划（根 Agent）→ 并行派发（子 Agent）→ 汇总。

- 规划阶段用确定性启发式决定子任务与推理强度（demo 占位，见 ADR-006）。
- 子 Agent 在 live 模式用 LLM + 工具循环，在 mock 模式用确定性输出。
- 并行派发用 LangGraph 的 ``Send`` 扇出，``results`` 用 reducer 合并。
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .capabilities import CapabilityRegistry
from .settings import Settings

Effort = Literal["low", "medium", "high"]
MAX_ITERATIONS = 6

# 推理强度启发式（demo 占位）：命中高风险关键词 → high，命中低风险关键词 → low，其余 medium。
_EFFORT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "high": ("架构", "重构", "安全", "设计", "复杂", "性能", "并发", "数据库"),
    "low": ("列出", "列表", "查看", "文件", "统计", "行数", "结构"),
}


class Task(TypedDict):
    id: str
    description: str
    effort: Effort


class AgentState(TypedDict, total=False):
    objective: str
    tasks: list[Task]
    task: Task  # 由 Send 注入到 worker
    results: Annotated[dict[str, str], merge_results]
    report: str


def merge_results(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    """合并各子 Agent 的结果（reducer）。"""
    return {**left, **right}


def estimate_effort(text: str) -> Effort:
    for level in ("high", "low"):
        if any(k in text for k in _EFFORT_KEYWORDS[level]):
            return level  # type: ignore[return-value]
    return "medium"


def plan_node(state: AgentState) -> dict:
    """根 Agent：把目标拆成子任务，并给出推理强度。"""
    objective: str = state["objective"]
    tasks: list[Task] = []

    if any(k in objective for k in ("列出", "列表", "文件", "结构", "目录")):
        tasks.append(
            {"id": "list_files", "description": "列出项目文件结构", "effort": "low"}
        )
    if any(k in objective for k in ("README", "readme", "总结", "定位", "简介")):
        tasks.append(
            {
                "id": "read_readme",
                "description": "阅读 README.md 并总结项目定位",
                "effort": "medium",
            }
        )
    if any(k in objective for k in ("依赖", "pyproject", "依赖关系")):
        tasks.append(
            {
                "id": "read_pyproject",
                "description": "阅读 pyproject.toml 并总结依赖",
                "effort": "medium",
            }
        )

    if not tasks:
        tasks.append(
            {
                "id": "general",
                "description": objective,
                "effort": estimate_effort(objective),
            }
        )
    return {"tasks": tasks}


def dispatch_workers(state: AgentState) -> list[Send]:
    """向每个子任务派发一个 worker（并行扇出）。"""
    return [
        Send("worker", {"objective": state["objective"], "task": task})
        for task in state["tasks"]
    ]


def _execute_tool(name: str, args: dict, tools: dict[str, BaseTool]) -> str:
    tool = tools.get(name)
    if tool is None:
        return f"未知工具: {name}"
    try:
        return str(tool.invoke(args))
    except Exception as exc:  # noqa: BLE001
        return f"工具执行失败: {exc}"


def _live_worker(
    objective: str,
    task: Task,
    model: BaseChatModel,
    tools: dict[str, BaseTool],
    registry: CapabilityRegistry,
) -> str:
    """真实模型：手动 ReAct 循环（绑定工具 → 调用 → 执行 → 回填）。"""
    model_with_tools = model.bind_tools(list(tools.values()))
    messages = [
        SystemMessage(content=registry.system_prompt()),
        HumanMessage(
            content=(
                f"总体目标: {objective}\n"
                f"当前子任务: {task['description']}\n"
                "请使用工具完成任务，并返回简洁结果。"
            )
        ),
    ]

    for _ in range(MAX_ITERATIONS):
        response = model_with_tools.invoke(messages)
        messages.append(response)
        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            content = getattr(response, "content", "") or ""
            return str(content)
        for tc in tool_calls:
            output = _execute_tool(tc["name"], tc["args"], tools)
            messages.append(ToolMessage(content=output, tool_call_id=tc["id"]))
    return "达到最大迭代次数，任务未完成。"


def _mock_worker(task: Task, tools: dict[str, BaseTool]) -> str:
    """mock 模式：确定性调用工具，不依赖模型。"""
    tid = task["id"]
    if tid == "list_files":
        return tools["list_files"].invoke({"path": "."})
    if tid == "read_readme":
        content = tools["read_file"].invoke({"path": "README.md"})
        lines = content.splitlines()[:6]
        return "已读取 README.md，摘要：\n" + "\n".join(lines)
    if tid == "read_pyproject":
        return tools["read_file"].invoke({"path": "pyproject.toml"})
    return f"(mock) 对任务「{task['description']}」返回确定性占位结果。"


def build_graph(
    settings: Settings, registry: CapabilityRegistry
) -> Any:
    """构建并编译委派图。"""
    model = settings.build_model()
    tools = {t.name: t for t in registry.tools}

    def worker(state: AgentState) -> dict:
        task = state["task"]
        if model is None:
            result = _mock_worker(task, tools)
        else:
            result = _live_worker(state["objective"], task, model, tools, registry)
        return {"results": {task["id"]: result}}

    def report_node(state: AgentState) -> dict:
        lines = []
        for task in state["tasks"]:
            rid = task["id"]
            res = state["results"].get(rid, "(无结果)")
            lines.append(f"[{task['effort']}] {task['description']}\n  → {res}")
        return {"report": "\n\n".join(lines)}

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("worker", worker)
    graph.add_node("report", report_node)

    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", dispatch_workers, ["worker"])
    graph.add_edge("worker", "report")
    graph.add_edge("report", END)

    return graph.compile()


def render_tree(tasks: list[Task]) -> str:
    """渲染委派树（demo 中为根 → 一层子节点）。"""
    if not tasks:
        return "  (无任务)"
    lines = []
    for i, task in enumerate(tasks):
        connector = "└─" if i == len(tasks) - 1 else "├─"
        lines.append(f"  {connector} {task['id']} [{task['effort']}]  {task['description']}")
    return "\n".join(lines)
