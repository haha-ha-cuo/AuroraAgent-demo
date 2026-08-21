"""强度分档对照实验（ADR-006 扩展）。

对同一任务分别以 low / medium / high 强度运行，用 judge 模型从
「完整性 / 准确性 / 简洁性」三个维度打分，对比质量分 vs token 成本。

运行：``python -m demo_agent.experiment [--task <id>] [--tiers low,medium,high] [--repeat N]``

注意：本实验走真实模型，会消耗 token；含 Blender 任务时会拉起本地 Blender。
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Any

from .capabilities import CapabilityRegistry
from .gate import ConfirmationGate, yes_confirm
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
    completeness: int
    accuracy: int
    conciseness: int
    reason: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency: float
    answer: str


# ---- 实验任务集 ----

EXPERIMENT_TASKS: list[ExperimentTask] = [
    ExperimentTask(
        id="summarize_readme",
        objective="总结 README.md 的项目定位与技术栈",
        task_desc="阅读 README.md 并总结项目定位与技术栈",
        reference=(
            "满分答案应覆盖：CodeX-like 全平台桌面 AI Agent 的定位；"
            "LangChain Core + LangGraph + MCP 技术栈；能力特化层与本地 API 管理；uv 管理 Python 环境。"
        ),
    ),
    ExperimentTask(
        id="compare_architecture",
        objective="对比 docs/architecture/overview.md 与 decisions.md，总结架构分层与 ADR 的对应关系",
        task_desc="阅读 docs/architecture/overview.md 和 docs/architecture/decisions.md，总结架构分层、各层职责，并说明各层对应的 ADR",
        reference=(
            "满分答案应覆盖：桌面壳 / Python Agent 运行时 / 基础设施层三层及职责；"
            "能力特化层、模型接入、委派树、推理强度、MCP、安全权限、eval 等 ADR 主题；"
            "并说明各主题与分层的对应关系，结构清晰。"
        ),
    ),
    ExperimentTask(
        id="blender_sphere",
        objective="打开本地 Blender 并创建一个球体",
        task_desc="使用 blender_create_sphere 工具在本地 Blender 中创建一个球体",
        reference=(
            "满分答案应：说明调用了本地 Blender（headless）工具；"
            "确认成功创建球体（给出球体名称/半径，或说明场景对象含 Sphere）；不虚构结果。"
        ),
    ),
]


# ---- judge ----

_JUDGE_PROMPT = """你是严格的评审专家。请从三个维度为候选答案打分，每个维度 1-5 分（5 为满分）。

任务：{task_desc}

参考标准（满分答案应覆盖的要点）：
{reference}

候选答案：
{answer}

请只输出一行 JSON，不要有任何其他文字：
{{"completeness": <1-5 整数>, "accuracy": <1-5 整数>, "conciseness": <1-5 整数>, "reason": "<一句话中文理由>"}}
"""


def _clamp(value: int, lo: int = 1, hi: int = 5) -> int:
    return max(lo, min(hi, value))


def parse_judge(text: str) -> dict | None:
    """解析 judge 输出为三维评分；失败返回 None。"""
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return {
            "completeness": _clamp(int(data["completeness"])),
            "accuracy": _clamp(int(data["accuracy"])),
            "conciseness": _clamp(int(data["conciseness"])),
            "reason": str(data.get("reason", "")),
        }
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _judge(
    model: Any, task_desc: str, reference: str, answer: str
) -> tuple[float, dict, str]:
    prompt = _JUDGE_PROMPT.format(task_desc=task_desc, reference=reference, answer=answer)
    for _ in range(2):
        try:
            resp = model.invoke(prompt)
            text = str(getattr(resp, "content", "") or "")
            parsed = parse_judge(text)
            if parsed is not None:
                score = round(
                    (parsed["completeness"] + parsed["accuracy"] + parsed["conciseness"]) / 3,
                    2,
                )
                return score, parsed, parsed["reason"]
        except Exception:  # noqa: BLE001
            continue
    default = {"completeness": 3, "accuracy": 3, "conciseness": 3}
    return 3.0, default, "judge 输出解析失败，回退默认分"


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
    # 对照实验模拟「已授权的用户」：写/执行放行（含 Blender）。
    gate = ConfirmationGate(confirm=yes_confirm)
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
                score, parsed, reason = _judge(judge_model, exp.task_desc, exp.reference, answer)
                rows.append(
                    TierResult(
                        tier=tier,
                        score=score,
                        completeness=parsed["completeness"],
                        accuracy=parsed["accuracy"],
                        conciseness=parsed["conciseness"],
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
        lines.append(
            f"  {'tier':<7}{'score':<7}{'c/a/s':<9}{'prompt':<9}{'completion':<11}{'total':<9}{'耗时':<8}"
        )
        for r in data["rows"]:
            sub = f"{r.completeness}/{r.accuracy}/{r.conciseness}"
            lines.append(
                f"  {r.tier:<7}{r.score:<7.2f}{sub:<9}{r.prompt_tokens:<9}"
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
