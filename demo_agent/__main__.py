"""CLI 入口：``python -m demo_agent [--yes] "目标"``。

- ``--yes``：确认门对写/执行操作全放行（用于非交互演示）。
- 交互终端：写/执行操作逐条提示确认。
- 非交互（无 --yes）：写/执行操作默认拒绝（安全默认）。
"""

from __future__ import annotations

import sys

from .capabilities import CapabilityRegistry
from .gate import ConfirmationGate, interactive_confirm, yes_confirm
from .graph import build_graph, render_tree
from .settings import Settings
from .tools import DEFAULT_TOOLS

DEFAULT_OBJECTIVE = "列出项目文件结构，并阅读 README.md 总结项目定位"


def _parse_args(argv: list[str]) -> tuple[bool, str]:
    """返回 (yes, objective)。"""
    yes = "--yes" in argv or "-y" in argv
    positional = [a for a in argv if not a.startswith("-")]
    objective = positional[0] if positional else DEFAULT_OBJECTIVE
    return yes, objective


def main() -> None:
    yes, objective = _parse_args(sys.argv[1:])
    settings = Settings.from_env()

    # 组装能力特化层：注入上下文与工具。
    registry = (
        CapabilityRegistry(name="demo")
        .with_context("你正在名为 demo 的仓库中工作，返回结果使用简体中文。")
        .with_context("写操作会经过确认门，未授权会被拒绝。")
    )
    for tool in DEFAULT_TOOLS:
        registry.with_tool(tool)

    # 确认门：--yes 全放行；交互终端逐条确认；非交互默认拒绝写/执行。
    if yes:
        gate = ConfirmationGate(confirm=yes_confirm)
        gate_desc = "--yes 全放行"
    elif sys.stdin.isatty():
        gate = ConfirmationGate(confirm=interactive_confirm)
        gate_desc = "交互确认"
    else:
        gate = ConfirmationGate()
        gate_desc = "非交互默认拒绝写/执行"

    print(f"目标: {objective}")
    print(f"模式: {settings.mode}")
    print(f"配置: {settings.redacted()}")
    print(f"确认门: {gate_desc}")

    graph = build_graph(settings, registry, gate)
    result = graph.invoke({"objective": objective, "results": {}})

    print("\n委派树（根 → 子 Agent）:")
    print(render_tree(result["tasks"]))

    print("\n汇总报告:")
    print(result["report"])


if __name__ == "__main__":
    main()
