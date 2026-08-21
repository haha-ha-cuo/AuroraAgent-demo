"""对照实验模块的确定性测试（不依赖真实模型）。"""

from demo_agent.experiment import parse_judge
from demo_agent.graph import EFFORT_CONFIGS


def test_effort_configs_cover_all_tiers():
    assert set(EFFORT_CONFIGS) == {"low", "medium", "high"}
    assert EFFORT_CONFIGS["high"].review is True
    assert EFFORT_CONFIGS["low"].review is False
    assert EFFORT_CONFIGS["high"].max_iterations >= EFFORT_CONFIGS["medium"].max_iterations
    # max_tokens 硬性区分档位
    assert (
        EFFORT_CONFIGS["low"].max_tokens
        < EFFORT_CONFIGS["medium"].max_tokens
        < EFFORT_CONFIGS["high"].max_tokens
    )


def test_parse_judge_valid():
    parsed = parse_judge(
        '{"completeness": 4, "accuracy": 5, "conciseness": 3, "reason": "完整但略啰嗦"}'
    )
    assert parsed == {
        "completeness": 4,
        "accuracy": 5,
        "conciseness": 3,
        "reason": "完整但略啰嗦",
    }


def test_parse_judge_with_extra_text():
    parsed = parse_judge(
        '我的评分是 {"completeness": 5, "accuracy": 5, "conciseness": 5, "reason": "很好"} 结束'
    )
    assert parsed["completeness"] == 5


def test_parse_judge_clamps_scores():
    parsed = parse_judge(
        '{"completeness": 99, "accuracy": -1, "conciseness": 3, "reason": "x"}'
    )
    assert parsed["completeness"] == 5
    assert parsed["accuracy"] == 1


def test_parse_judge_garbage_returns_none():
    assert parse_judge("这不是 JSON") is None
    assert parse_judge("") is None
