"""eval 集的回归测试：全部 fixture 应通过。"""

from demo_agent.eval import FIXTURES, run_eval


def test_all_fixtures_pass():
    results = run_eval(FIXTURES)
    failed = [r for r in results if not r.passed]
    assert not failed, [
        f"{r.case_id}: {r.details}" for r in failed
    ]
