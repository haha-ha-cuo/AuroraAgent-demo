"""最小 eval 集（ADR-006）。

用确定性 mock 模式跑一组任务 fixture，校验两件事：
1. 规划：任务识别是否准确、推理强度分档是否正确；
2. 端到端：结果是否包含期望内容。

零 token 成本、可反复跑，用于校准推理强度启发式；后续 LLM 规划器
落地后，用同一套 fixture 即可对比。

运行：``python -m demo_agent.eval``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .capabilities import CapabilityRegistry
from .gate import ConfirmationGate
from .graph import build_graph
from .settings import Settings
from .tools import DEFAULT_TOOLS

Check = Callable[[dict], tuple[bool, str]]


@dataclass
class EvalCase:
    id: str
    objective: str
    checks: list[Check] = field(default_factory=list)


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    details: list[str]


# ---- 检查器 ----


def tasks_include(*ids: str) -> Check:
    """断言规划产出了指定的任务 id。"""

    def check(result: dict) -> tuple[bool, str]:
        got = {t["id"] for t in result["tasks"]}
        missing = [i for i in ids if i not in got]
        if missing:
            return False, f"缺少任务 {missing}（实际 {sorted(got)}）"
        return True, f"任务含 {list(ids)}"

    return check


def effort_is(task_id: str, effort: str) -> Check:
    """断言某任务的推理强度。"""

    def check(result: dict) -> tuple[bool, str]:
        for t in result["tasks"]:
            if t["id"] == task_id:
                ok = t["effort"] == effort
                return ok, f"{task_id} 强度 {t['effort']}（期望 {effort}）"
        return False, f"无任务 {task_id}"

    return check


def result_contains(task_id: str, *substrings: str) -> Check:
    """断言某任务的结果包含指定子串。"""

    def check(result: dict) -> tuple[bool, str]:
        text = result["results"].get(task_id, "")
        missing = [s for s in substrings if s not in text]
        if missing:
            return False, f"{task_id} 结果缺少 {missing}"
        return True, f"{task_id} 结果包含 {list(substrings)}"

    return check


# ---- fixtures（十几个任务）----

FIXTURES: list[EvalCase] = [
    # 规划：任务识别
    EvalCase("plan_list_files", "列出项目文件结构", [
        tasks_include("list_files"),
        effort_is("list_files", "low"),
    ]),
    EvalCase("plan_read_readme", "阅读 README.md 总结项目定位", [
        tasks_include("read_readme"),
        effort_is("read_readme", "medium"),
    ]),
    EvalCase("plan_combined", "列出项目文件结构，并阅读 README.md 总结项目定位", [
        tasks_include("list_files", "read_readme"),
    ]),
    EvalCase("plan_read_pyproject", "查看 pyproject.toml 的依赖", [
        tasks_include("read_pyproject"),
    ]),
    EvalCase("plan_write", "写入文件", [
        tasks_include("write_file"),
    ]),
    # 规划：推理强度分档
    EvalCase("effort_high", "重构数据库层并做安全审计", [
        tasks_include("general"),
        effort_is("general", "high"),
    ]),
    EvalCase("effort_low", "统计代码行数", [
        tasks_include("general"),
        effort_is("general", "low"),
    ]),
    EvalCase("effort_medium", "随便做点常规事情", [
        tasks_include("general"),
        effort_is("general", "medium"),
    ]),
    # 端到端（mock，确定性）
    EvalCase("e2e_list_files", "列出项目文件结构", [
        result_contains("list_files", "README.md"),
    ]),
    EvalCase("e2e_read_readme", "阅读 README.md 总结项目定位", [
        result_contains("read_readme", "CodeX", "AI Agent"),
    ]),
    EvalCase("e2e_read_pyproject", "查看 pyproject.toml 的依赖", [
        result_contains("read_pyproject", "langgraph"),
    ]),
    EvalCase("e2e_write_denied", "写入文件", [
        result_contains("write_file", "拒绝"),
    ]),
]


def _default_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry(name="eval")
    for tool in DEFAULT_TOOLS:
        reg.with_tool(tool)
    return reg


def run_eval(cases: list[EvalCase]) -> list[EvalResult]:
    """在 mock 模式下跑所有 fixture，返回逐项结果。"""
    # 强制 mock：eval 与密钥/网络无关，保证确定性、零成本。
    settings = Settings(
        api_key=None, base_url="https://api.openai.com/v1", model="gpt-4o-mini"
    )
    gate = ConfirmationGate()  # 写默认拒绝
    graph = build_graph(settings, _default_registry(), gate)

    results: list[EvalResult] = []
    for case in cases:
        state = graph.invoke({"objective": case.objective, "results": {}})
        details: list[str] = []
        passed = True
        for check in case.checks:
            ok, msg = check(state)
            details.append(("✓ " if ok else "✗ ") + msg)
            passed = passed and ok
        results.append(EvalResult(case.id, passed, details))
    return results


def main() -> int:
    results = run_eval(FIXTURES)
    n_pass = sum(1 for r in results if r.passed)

    print(f"最小 eval 集（mock 模式，{len(results)} 项）\n")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.case_id}")
        for d in r.details:
            print(f"      {d}")

    print(f"\n结果：{n_pass}/{len(results)} 通过")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
