"""LangGraph 委派图：规划（根 Agent）→ 并行派发（子 Agent）→ 汇总。

- 规划阶段用确定性启发式决定子任务与推理强度（demo 占位，见 ADR-006）。
- 子 Agent 在 live 模式用 LLM + 工具循环，在 mock 模式用确定性输出。
- 并行派发用 LangGraph 的 ``Send`` 扇出，``results`` 用 reducer 合并。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Callable, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .capabilities import CapabilityRegistry
from .gate import ConfirmationGate
from .settings import Settings
from .tools import risk_of

Effort = Literal["low", "medium", "high"]

# 推理强度启发式（demo 占位）：命中高风险关键词 → high，命中低风险关键词 → low，其余 medium。
_EFFORT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "high": ("架构", "重构", "安全", "设计", "复杂", "性能", "并发", "数据库"),
    "low": ("列出", "列表", "查看", "文件", "统计", "行数", "结构"),
}


@dataclass(frozen=True)
class EffortConfig:
    """推理强度如何影响真实 worker 行为。

    注：自评（review）在对照实验中为负收益，已移除（见 ADR-006）。
    """

    brief: str  # 注入到子任务里的输出要求
    max_iterations: int
    max_tokens: int  # 单次生成 token 上限（部分推理模型不强制生效）


EFFORT_CONFIGS: dict[str, EffortConfig] = {
    "low": EffortConfig(brief="请简明扼要地回答，不超过 60 字。", max_iterations=3, max_tokens=256),
    "medium": EffortConfig(brief="请给出完整、准确的回答。", max_iterations=6, max_tokens=1024),
    "high": EffortConfig(brief="请给出完整、准确且结构化的回答。", max_iterations=6, max_tokens=2048),
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

    if any(k in objective for k in ("列出", "列表", "结构", "目录", "有哪些文件")):
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
    if any(k in objective for k in ("写入", "写文件", "创建文件", "生成文件")):
        tasks.append(
            {"id": "write_file", "description": "写入演示文件", "effort": "medium"}
        )
    if any(k in objective for k in ("球体", "blender", "Blender", "3D", "建模")):
        tasks.append(
            {"id": "blender", "description": "在本地 Blender 中创建球体", "effort": "high"}
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


def _execute_tool(
    name: str, args: dict, tools: dict[str, BaseTool], gate: ConfirmationGate
) -> str:
    tool = tools.get(name)
    if tool is None:
        return f"未知工具: {name}"
    risk = risk_of(name)
    if not gate.request(f"工具 {name} 参数 {args}", risk):
        return f"操作被确认门拒绝（risk={risk}）: {name}"
    try:
        return str(tool.invoke(args))
    except Exception as exc:  # noqa: BLE001
        return f"工具执行失败: {exc}"


def _extract_usage(msg: Any) -> dict[str, int]:
    """从消息里提取 token 用量（优先 usage_metadata，回退 llm_output）。"""
    um = getattr(msg, "usage_metadata", None)
    if um:
        return {
            "prompt": um.get("input_tokens", 0),
            "completion": um.get("output_tokens", 0),
            "total": um.get("total_tokens", 0),
        }
    llm_out = getattr(msg, "llm_output", {}) or {}
    tu = llm_out.get("token_usage", {}) or {}
    return {
        "prompt": tu.get("prompt_tokens", 0),
        "completion": tu.get("completion_tokens", 0),
        "total": tu.get("total_tokens", 0),
    }


def _accumulate(msg: Any, usage: list | None) -> None:
    if usage is not None:
        usage.append(_extract_usage(msg))


def _live_worker(
    objective: str,
    task: Task,
    model: BaseChatModel,
    tools: dict[str, BaseTool],
    registry: CapabilityRegistry,
    gate: ConfirmationGate,
    usage: list | None = None,
) -> str:
    """真实模型：手动 ReAct 循环，并按推理强度差异化行为。"""
    config = EFFORT_CONFIGS.get(task["effort"], EFFORT_CONFIGS["medium"])
    model_with_tools = model.bind_tools(list(tools.values()), max_tokens=config.max_tokens)
    messages = [
        SystemMessage(content=registry.system_prompt()),
        HumanMessage(
            content=(
                f"总体目标: {objective}\n"
                f"当前子任务: {task['description']}\n"
                f"{config.brief}\n请使用工具完成任务，并返回结果。"
            )
        ),
    ]

    answer = ""
    for _ in range(config.max_iterations):
        response = model_with_tools.invoke(messages)
        _accumulate(response, usage)
        messages.append(response)
        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            answer = str(getattr(response, "content", "") or "")
            break
        for tc in tool_calls:
            output = _execute_tool(tc["name"], tc["args"], tools, gate)
            messages.append(ToolMessage(content=output, tool_call_id=tc["id"]))

    if not answer:
        answer = "达到最大迭代次数，任务未完成。"

    return answer


def run_task(
    settings: Settings,
    registry: CapabilityRegistry,
    gate: ConfirmationGate,
    task: Task,
    objective: str,
    usage: list | None = None,
) -> str:
    """公开入口：直接执行单个子任务（供 eval / 对照实验复用）。"""
    model = settings.build_model()
    tools = {t.name: t for t in registry.tools}
    if model is None:
        return _mock_worker(task, tools, gate)
    return _live_worker(objective, task, model, tools, registry, gate, usage)


def _mock_worker(task: Task, tools: dict[str, BaseTool], gate: ConfirmationGate) -> str:
    """mock 模式：确定性调用工具，不依赖模型（同样经过确认门）。"""
    tid = task["id"]
    if tid == "list_files":
        return _execute_tool("list_files", {"path": "."}, tools, gate)
    if tid == "read_readme":
        content = _execute_tool("read_file", {"path": "README.md"}, tools, gate)
        lines = content.splitlines()[:6]
        return "已读取 README.md，摘要：\n" + "\n".join(lines)
    if tid == "read_pyproject":
        return _execute_tool("read_file", {"path": "pyproject.toml"}, tools, gate)
    if tid == "write_file":
        return _execute_tool(
            "write_file",
            {"path": "demo_output.txt", "content": "demo 确认门写入\n"},
            tools,
            gate,
        )
    if tid == "blender":
        return _execute_tool("blender_create_sphere", {"radius": 1.0}, tools, gate)
    return f"(mock) 对任务「{task['description']}」返回确定性占位结果。"


def build_graph(
    settings: Settings,
    registry: CapabilityRegistry,
    gate: ConfirmationGate | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> Any:
    """构建并编译委派图。

    ``gate`` 为 None 时使用安全默认（读放行、写/执行默认拒绝）。
    ``on_event`` 可选，用于把规划/任务进度流式回调给调用方（如 WebSocket 服务）。
    """
    model = settings.build_model()
    tools = {t.name: t for t in registry.tools}
    if gate is None:
        gate = ConfirmationGate()

    def emit(event: dict) -> None:
        if on_event is not None:
            on_event(event)

    def plan(state: AgentState) -> dict:
        out = plan_node(state)
        emit({"type": "plan", "tasks": out.get("tasks", [])})
        return out

    def worker(state: AgentState) -> dict:
        task = state["task"]
        emit(
            {
                "type": "task_start",
                "task_id": task["id"],
                "description": task["description"],
                "effort": task["effort"],
            }
        )
        if model is None:
            result = _mock_worker(task, tools, gate)
        else:
            result = _live_worker(
                state["objective"], task, model, tools, registry, gate
            )
        emit({"type": "task_result", "task_id": task["id"], "result": result})
        return {"results": {task["id"]: result}}

    def report_node(state: AgentState) -> dict:
        lines = []
        for task in state["tasks"]:
            rid = task["id"]
            res = state["results"].get(rid, "(无结果)")
            lines.append(f"[{task['effort']}] {task['description']}\n  → {res}")
        report = "\n\n".join(lines)
        emit({"type": "report", "report": report})
        return {"report": report}

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan)
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
