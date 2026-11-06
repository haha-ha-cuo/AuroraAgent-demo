# 评估与校准

以下命令在 AuroraHarness 仓库根目录执行。

## 离线基准

```sh
uv run aurora eval
uv run aurora eval --list
uv run aurora eval --case dependency_denied --json
```

默认运行 14 个确定性用例。每项使用独立临时工作区，规划器根据任务指令识别操作，实际的计划校验、确认门和文件工具负责执行。断言核对任务、档位、工具结果和最终文件。例如拒绝写入时，依赖该文件的读取应被阻断，独立读取仍应成功。

报告逐项列出期望值与观测值，最后汇总通过数。全部通过返回 0，验收失败返回 1，选择了不存在的用例等参数错误返回 2。默认运行无需网络、模型凭据或 token。可在 `src/agent/src/aurora/eval/fixtures.py` 增加数据用例。

## 模型对照实验

```sh
uv run aurora eval --live --list
uv run aurora eval --live --task compare_architecture --tiers low,high --repeat 2 --json
```

只有显式选择 `--live` 并运行实验才会调用模型并产生 token 用量。CLI 读取 `AGENT_MODEL`、`AGENT_API_KEY`（也接受 `OPENAI_API_KEY`），兼容端点可通过 `AGENT_BASE_URL` 指定。默认对两个文本任务各跑三档，每档一次。

| 任务 | 固定输入与要求 |
| --- | --- |
| `summarize_readme` | 根据内置 README 说明用途、输入和技术实现 |
| `compare_architecture` | 对比同步提交和内存队列两条路径，判断进程退出时的数据边界 |

同一任务的各档和各次重复使用相同项目材料。worker 按所选档位生成答案，judge 根据材料、评分标准和候选答案盲评完整性、准确性、简洁性，各项为 1–5 分，均值为本次得分。无效评分会让该次实验失败。

报告提供逐次结果，并按任务与档位、跨任务档位分别汇总。worker 与 judge 分别记录请求耗时及模型返回的输入、输出、总 token。供应商缺报的用量显示为未知。平均分只计成功获得评分的试次，需结合失败次数、重复试验和人工抽检解读。

离线基准验证确定性规划与执行。当前自动回归通过注入模型和模拟传输核对对照请求、评分格式与用量统计。供应商的实际质量和费用须在指定端点运行实验后读取。[推理强度](reasoning-effort.md) · [ADR-006](decisions.md#adr-006)
