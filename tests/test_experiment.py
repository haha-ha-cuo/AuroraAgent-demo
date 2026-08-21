"""对照实验模块的确定性测试（不依赖真实模型）。"""

from demo_agent.experiment import parse_judge
from demo_agent.graph import EFFORT_CONFIGS


def test_effort_configs_cover_all_tiers():
    assert set(EFFORT_CONFIGS) == {"low", "medium", "high"}
    assert EFFORT_CONFIGS["high"].review is True
    assert EFFORT_CONFIGS["low"].review is False
    assert EFFORT_CONFIGS["high"].max_iterations >= EFFORT_CONFIGS["medium"].max_iterations


def test_parse_judge_valid():
    score, reason = parse_judge('{"score": 4, "reason": "覆盖了大部分要点"}')
    assert score == 4
    assert reason == "覆盖了大部分要点"


def test_parse_judge_with_extra_text():
    score, _ = parse_judge('我的评分是 {"score": 5, "reason": "很完整"} 结束')
    assert score == 5


def test_parse_judge_clamps_score():
    assert parse_judge('{"score": 99, "reason": "x"}')[0] == 5
    assert parse_judge('{"score": -1, "reason": "x"}')[0] == 1


def test_parse_judge_garbage_returns_none():
    assert parse_judge("这不是 JSON") is None
    assert parse_judge("") is None
