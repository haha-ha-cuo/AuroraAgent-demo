"""强度分档对照实验（ADR-006 扩展）。

对同一任务分别以 low / medium / high 强度运行，用 judge 模型评分，
对比「质量分 vs token 成本」，用于校准推理强度分档。

运行：``python -m demo_agent.experiment [--task <id>] [--tiers low,medium,high] [--repeat N]``

注意：本实验走真实模型，会消耗 token。
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Any

from .capabilities import CapabilityRegistry
from .gate import ConfirmationGate
from .graph import EFFORT_CONFIGS, run_task
from .settings import Settings
from .tools import DEFAULT_TOOLS

EFFORT_TIERS = ["low", "medium", "high"]


@dataclass
class ExperimentTask:
    id: str
    objective: str
    task_desc: str
    reference: str


@dataclass
class TierResult:
    tier: str
    score: float
    reason: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency: float
    answer: str


# ---- 实验任务集（各带一份满分参考标准）----

EXPERIMENT_TASKS: list[ExperimentTask] = [
    ExperimentTask(
        id="summarize_readme",
        objective="总结 README.md 的项目定位与技术栈",
        task_desc="阅读 README.md 并总结项目定位与技术栈",
        reference=(
            "满分答案应覆盖：CodeX-like 全平台桌面 AI Agent 的定位；"
            "LangChain Core + LangGraph + MCP 技术栈；"
            "能力特化层与本地 API 管理；uv 管理 Python 环境。"
        ),
    ),
    ExperimentTask(
        id="summarize_adr",
        objective="总结 docs/architecture/decisions.md 里的 ADR 主题",
        task_desc="阅读 docs/architecture/decisions.md 并总结各条 ADR 的主题",
        reference=(
            "满分答案应覆盖：能力特化层与缓存解耦、模型远程 API + 本地管理、"
            "直接用 langchain-core + langgraph、委派失败语义、安全权限模型、eval 策略。"
        ),
    ),
]


# ---- judge ----

_JUDGE_PROMPT = """你是严格的评审专家。请根据参考标准，为候选答案评分（1-5 整数，5 为满分）。

任务：{task_desc}

参考标准（满分答案应覆盖的要点）：
{reference}

候选答案：
{answer}

请只输出一行 JSON，不要有任何其他文字：
{{"score": <1-5 整数>, "reason": "<一句话中文理由>"}}
"""


def parse_judge(text: str) -> tuple[float, str] | None:
    """从 judge 输出里解析 (score, reason)；失败返回 None。"""
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        score = float(data.get("score", 3))
        score = max(1.0, min(5.0, score))
        return score, str(data.get("reason", ""))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _judge(model: Any, task_desc: str, reference: str, answer: str) -> tuple[float, str]:
    prompt = _JUDGE_PROMPT.format(task_desc=task_desc, reference=reference, answer=answer)
    for _ in range(2):
        try:
            resp = model.invoke(prompt)
            text = str(getattr(resp, "content", "") or "")
            parsed = parse_judge(text)
            if parsed is not None:
                return parsed
        except Exception:  # noqa: BLE001
            continue
    return 3.0, "judge 输出解析失败，回退默认分"


# ---- 实验执行 ----


def _registry() -> CapabilityRegistry:
    reg = CapabilityRegistry(name="experiment")
    for tool in DEFAULT_TOOLS:
        reg.with_tool(tool)
    return reg


def run_experiment(
    tasks: list[ExperimentTask],
    tiers: list[str],
    settings: Settings,
    repeat: int = 1,
) -> dict[str, dict]:
    """对每个任务、每个强度档跑 ``repeat`` 次，返回原始结果。"""
    registry = _registry()
    gate = ConfirmationGate()
    judge_model = settings.build_model()

    report: dict[str, dict] = {}
    for exp in tasks:
        rows: list[TierResult] = []
        for tier in tiers:
            for _ in range(repeat):
                usage: list = []
                task = {"id": exp.id, "description": exp.task_desc, "effort": tier}
                t0 = time.perf_counter()
                answer = run_task(settings, registry, gate, task, exp.objective, usage=usage)
                latency = time.perf_counter() - t0
                score, reason = _judge(judge_model, exp.task_desc, exp.reference, answer)
                rows.append(
                    TierResult(
                        tier=tier,
                        score=score,
                        reason=reason,
                        prompt_tokens=sum(u["prompt"] for u in usage),
                        completion_tokens=sum(u["completion"] for u in usage),
                        total_tokens=sum(u["total"] for u in usage),
                        latency=latency,
                        answer=answer,
                    )
                )
        report[exp.id] = {"task": exp, "rows": rows}
    return report


# ---- 渲染 ----

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def render(report: dict[str, dict], tiers: list[str]) -> str:
    lines: list[str] = []

    for exp_id, data in report.items():
        exp: ExperimentTask = data["task"]
        lines.append(f"\n任务: {exp_id} — {exp.task_desc}")
        lines.append(f"  {'tier':<7}{'score':<7}{'prompt':<9}{'completion':<11}{'total':<9}{'耗时':<8}")
        for r in data["rows"]:
            lines.append(
                f"  {r.tier:<7}{r.score:<7.1f}{r.prompt_tokens:<9}"
                f"{r.completion_tokens:<11}{r.total_tokens:<9}{r.latency:<8.2f}"
            )
        for tier in tiers:
            r = next((x for x in data["rows"] if x.tier == tier), None)
            if r:
                lines.append(f"    judge[{tier}]: {r.reason}")

    # 分档汇总
    agg = {tier: {"scores": [], "tokens": [], "latencies": []} for tier in tiers}
    for data in report.values():
        for r in data["rows"]:
            agg[r.tier]["scores"].append(r.score)
            agg[r.tier]["tokens"].append(r.total_tokens)
            agg[r.tier]["latencies"].append(r.latency)

    lines.append("\n=== 分档汇总（跨任务平均） ===")
    lines.append(f"  {'tier':<7}{'平均分':<8}{'平均token':<12}{'平均耗时':<8}")
    for tier in tiers:
        a = agg[tier]
        lines.append(
            f"  {tier:<7}{_mean(a['scores']):<8.2f}{_mean(a['tokens']):<12.0f}{_mean(a['latencies']):<8.2f}"
        )

    # 档位间增量
    lines.append("\n=== 档位增量（相对上一档） ===")
    prev: dict[str, float] | None = None
    for tier in tiers:
        cur = {"score": _mean(agg[tier]["scores"]), "tokens": _mean(agg[tier]["tokens"])}
        if prev is not None:
            d_score = cur["score"] - prev["score"]
            d_tokens = cur["tokens"] - prev["tokens"]
            lines.append(
                f"  {tier}: 分数 {prev['score']:.2f}→{cur['score']:.2f} "
                f"({d_score:+.2f})，token {prev['tokens']:.0f}→{cur['tokens']:.0f} ({d_tokens:+.0f})"
            )
        prev = cur

    return "\n".join(lines)


def _parse_args(argv: list[str]) -> tuple[list[str], list[str], int]:
    tiers = EFFORT_TIERS
    task_ids: list[str] | None = None
    repeat = 1
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--tiers" and i + 1 < len(argv):
            tiers = [t.strip() for t in argv[i + 1].split(",")]
            i += 2
        elif a == "--task" and i + 1 < len(argv):
            task_ids = [argv[i + 1]]
            i += 2
        elif a == "--repeat" and i + 1 < len(argv):
            repeat = max(1, int(argv[i + 1]))
            i += 2
        else:
            i += 1
    return task_ids or [], tiers, repeat


def main() -> int:
    task_ids, tiers, repeat = _parse_args(sys.argv[1:])
    settings = Settings.from_env()

    if settings.mode != "live":
        print("错误：对照实验需要真实模型（live 模式）。请先在 .env 配置密钥。")
        return 2

    tasks = [t for t in EXPERIMENT_TASKS if not task_ids or t.id in task_ids]
    if not tasks:
        print(f"未找到任务，可用 id：{[t.id for t in EXPERIMENT_TASKS]}")
        return 2

    print(f"模式: {settings.mode} | 模型: {settings.model}")
    print(
        f"任务数: {len(tasks)} | 档位: {tiers} | 每档重复: {repeat} 次 | "
        f"预计 agent 调用: {len(tasks) * len(tiers) * repeat} 次 + 等量 judge 调用\n"
    )

    t0 = time.perf_counter()
    report = run_experiment(tasks, tiers, settings, repeat)
    total = time.perf_counter() - t0

    print(render(report, tiers))
    print(f"\n实验总耗时: {total:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
