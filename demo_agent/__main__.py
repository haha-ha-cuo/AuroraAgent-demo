"""CLI 入口：``python -m demo_agent "目标"``。"""

from __future__ import annotations

import sys

from .capabilities import CapabilityRegistry
from .graph import build_graph, render_tree
from .settings import Settings
from .tools import DEFAULT_TOOLS

DEFAULT_OBJECTIVE = "列出项目文件结构，并阅读 README.md 总结项目定位"


def main() -> None:
    settings = Settings.from_env()

    # 组装能力特化层：注入上下文与只读工具。
    registry = (
        CapabilityRegistry(name="demo")
        .with_context("你正在名为 demo 的仓库中工作，返回结果使用简体中文。")
        .with_context("只做只读分析，不修改任何文件。")
    )
    for tool in DEFAULT_TOOLS:
        registry.with_tool(tool)

    objective = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OBJECTIVE

    print(f"目标: {objective}")
    print(f"模式: {settings.mode}")
    print(f"配置: {settings.redacted()}")

    graph = build_graph(settings, registry)
    result = graph.invoke({"objective": objective, "results": {}})

    print("\n委派树（根 → 子 Agent）:")
    print(render_tree(result["tasks"]))

    print("\n汇总报告:")
    print(result["report"])


if __name__ == "__main__":
    main()
