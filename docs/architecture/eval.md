# 评估与校准（eval）

> 对应 [ADR-006](decisions.md#adr-006)。最小 eval 集用于校准「任务识别 + 推理强度分档」，是后续把启发式规划器升级为 LLM 规划器时的**同一把尺子**。

## 为什么需要

「自适应推理强度」要成立，前提是能回答：*高强度档位是否真的更优？* 没有基准，强度分档就是拍脑袋。最小 eval 集用**确定性、零成本**的方式先锁定当前启发式的正确性，后续再叠加 judge 与成本曲线。

## 设计取舍

- **mock 模式运行**：不依赖密钥与网络，零 token 成本，可反复跑、可进 CI。
- **两类断言**：
  1. **规划**：任务识别（`tasks_include`）与强度分档（`effort_is`）；
  2. **端到端**：结果包含期望内容（`result_contains`）。
- **fixture 是数据不是代码**：新增用例只需往 `FIXTURES` 列表加一个 `EvalCase`。

## 运行

```bash
uv run python -m demo_agent.eval
```

输出逐项 PASS/FAIL 与断言详情，末尾汇总 `N/M 通过`；任一失败返回非零退出码。

```text
最小 eval 集（mock 模式，12 项）

[PASS] plan_list_files
      ✓ 任务含 ['list_files']
      ✓ list_files 强度 low（期望 low）
...
结果：12/12 通过
```

同时纳入 pytest 回归：`tests/test_eval.py` 断言全部 fixture 通过，任何改动破坏规划/分档都会在 `uv run pytest` 暴露。

## 新增 fixture

```python
from demo_agent.eval import EvalCase, tasks_include, effort_is, result_contains

EvalCase(
    "my_case",
    "某条任务目标",
    [
        tasks_include("read_readme"),
        effort_is("read_readme", "medium"),
        result_contains("read_readme", "关键词"),
    ],
)
```

- `tasks_include(*ids)`：断言规划产出这些任务；
- `effort_is(task_id, level)`：断言某任务强度；
- `result_contains(task_id, *substrings)`：断言某任务结果包含子串。

## 当前覆盖与局限

- 覆盖 12 项：任务识别（列文件/读 README/读 pyproject/写文件）、强度分档（high/low/medium）、端到端结果、确认门拒绝写。
- **局限**：只校验确定性行为，不评估开放式回答的质量；无法量化「高强度比低强度好多少」。这两点需要引入 judge（模型打分）与成本/质量曲线，见 [ADR-006](decisions.md#adr-006) 待决策项。
