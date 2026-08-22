from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class PlanState(TypedDict):
    objective: str
    tasks: list[dict[str, str | None]]


class MockAgent:
    """Deterministic LangGraph-backed planner and worker used without credentials."""

    def __init__(self, step_delay: float = 0.01) -> None:
        self.step_delay = step_delay
        graph = StateGraph(PlanState)
        graph.add_node("planner", self._plan_node)
        graph.add_edge(START, "planner")
        graph.add_edge("planner", END)
        self._graph = graph.compile()

    @staticmethod
    def _plan_node(state: PlanState) -> dict[str, list[dict[str, str | None]]]:
        objective = state["objective"].strip()
        return {
            "tasks": [
                {"key": "analyse", "parent_key": None, "description": f"分析目标：{objective}", "effort": "medium"},
                {"key": "execute", "parent_key": None, "description": "执行核心任务", "effort": "high"},
                {"key": "verify", "parent_key": "execute", "description": "验证执行结果", "effort": "medium"},
                {"key": "report", "parent_key": None, "description": "汇总结论", "effort": "low"},
            ]
        }

    async def plan(self, objective: str) -> list[dict[str, str | None]]:
        result = await self._graph.ainvoke({"objective": objective, "tasks": []})
        return result["tasks"]

    async def execute(self, description: str, objective: str) -> str:
        await asyncio.sleep(self.step_delay)
        if "[fail]" in objective and "执行核心" in description:
            raise RuntimeError("mock worker failure requested by objective")
        return f"已完成：{description}"

    @staticmethod
    def report(objective: str, outputs: list[str]) -> str:
        body = "\n".join(f"- {output}" for output in outputs)
        return f"## 执行完成\n\n目标：{objective}\n\n{body}"
