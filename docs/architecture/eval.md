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

## 强度分档对照实验（judge）

最小 eval 集只锁确定性行为，回答不了「高强度档位值不值」。对照实验对此：对**同一任务分别用 low / medium / high 强度运行**，再用 judge 模型打分，输出质量分 vs token 成本的对比。

```bash
# 默认：全部任务 × 三档 × 各 1 次（走真实模型，会消耗 token）
uv run python -m demo_agent.experiment

# 只跑一个任务 / 限制档位 / 每档重复 N 次取平均
uv run python -m demo_agent.experiment --task summarize_readme --tiers low,high --repeat 3
```

推理强度会真实影响 worker 行为（见 [推理强度](reasoning-effort.md) 与 `demo_agent/graph.py::EFFORT_CONFIGS`）：

| 档位 | 行为差异 |
| --- | --- |
| low | 简答（≤60 字）+ `max_tokens=256`（尝试限制）、迭代上限 3、无 review |
| medium | 完整回答 + `max_tokens=1024`、迭代上限 6、无 review |
| high | 完整回答 + `max_tokens=2048`、迭代上限 6、定向批判 + 增量修补（**实验中为负收益**） |

> 已知问题：`max_tokens` 对 deepseek-v4-flash 这类推理模型不强制生效（实测 `max_tokens=64` 仍产出 205 输出 token），档位差异实际主要来自 prompt 指令；见下方「局限」。

judge 从三个维度打分（各 1-5，取平均为最终分）：**完整性 / 准确性 / 简洁性**，用于给出部分分、避免单一满分饱和。

任务集覆盖易/难两类：易（总结单文件）、难（跨文件架构对比）、**真机（调用本地 Blender 创建球体，execute 级工具）**。

输出示例：

```text
任务: summarize_readme — 阅读 README.md 并总结项目定位与技术栈
  tier    score  prompt  completion  total    耗时
  low     3.0    1200    180        1380     2.1
  medium  4.0    1600    260        1860     2.8
  high    5.0    2200    420        2620     4.9

=== 分档汇总（跨任务平均） ===
  tier    平均分  平均token   平均耗时
  low     3.00    1380        2.10
  medium  4.00    1860        2.80
  high    5.00    2620        4.90
```

## 当前覆盖与局限

- **确定性 eval**：14 项，锁任务识别 + 强度分档 + 端到端 + 确认门（mock，零成本）。
- **对照实验**：多维 judge（完整/准确/简洁）+ 三档成本/质量对比（live，消耗 token），含 Blender 真机任务。
- **局限**：
  - judge 是单一模型打分，存在方差与偏差；可靠结论需要 `--repeat` 多次取平均 + 人工抽检；
  - `max_tokens` 对推理模型不强制生效（需 `max_completion_tokens`，langchain-openai 未暴露）；
  - **high 档自评（含定向批判）在实验中为负收益**：中等任务 medium 已触顶，自评要么冗余扩写、要么臆造缺陷（Blender 任务因自评从 5.0 掉到 2.67）；
  - 见 [ADR-006](decisions.md#adr-006) 待决策项。
