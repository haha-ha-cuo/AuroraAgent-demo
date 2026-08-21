"""mock 模式下的图接线冒烟测试（无需真实密钥）。"""

from demo_agent.capabilities import CapabilityRegistry
from demo_agent.graph import build_graph, estimate_effort
from demo_agent.settings import Settings
from demo_agent.tools import DEFAULT_TOOLS


def _registry() -> CapabilityRegistry:
    reg = CapabilityRegistry(name="test")
    for tool in DEFAULT_TOOLS:
        reg.with_tool(tool)
    return reg


def _mock_settings() -> Settings:
    return Settings(
        api_key=None,
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    )


def test_estimate_effort_levels():
    assert estimate_effort("列出文件结构") == "low"
    assert estimate_effort("重构数据库层并做安全审计") == "high"
    assert estimate_effort("随便做点常规事情") == "medium"


def test_graph_mock_run_delegates_and_reports():
    graph = build_graph(_mock_settings(), _registry())
    result = graph.invoke(
        {
            "objective": "列出项目文件结构，并阅读 README.md 总结项目定位",
            "results": {},
        }
    )

    task_ids = {t["id"] for t in result["tasks"]}
    assert "list_files" in task_ids
    assert "read_readme" in task_ids

    assert "list_files" in result["results"]
    assert "read_readme" in result["results"]
    assert result["report"]
