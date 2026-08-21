"""确认门（ADR-005）策略与 mock 写操作演示的测试。"""

from demo_agent.capabilities import CapabilityRegistry
from demo_agent.gate import ConfirmationGate, yes_confirm
from demo_agent.graph import build_graph
from demo_agent.settings import Settings
from demo_agent.tools import DEFAULT_TOOLS, risk_of


def _registry() -> CapabilityRegistry:
    reg = CapabilityRegistry(name="test")
    for tool in DEFAULT_TOOLS:
        reg.with_tool(tool)
    return reg


def _mock_settings() -> Settings:
    return Settings(api_key=None, base_url="https://api.openai.com/v1", model="gpt-4o-mini")


def test_read_auto_allowed():
    gate = ConfirmationGate()
    assert gate.request("读取文件", "read") is True


def test_write_denied_without_confirm():
    gate = ConfirmationGate()
    assert gate.request("写入文件", "write") is False


def test_execute_denied_by_default():
    gate = ConfirmationGate()
    assert gate.request("运行命令", "execute") is False


def test_write_allowed_with_yes_confirm():
    gate = ConfirmationGate(confirm=yes_confirm)
    assert gate.request("写入文件", "write") is True


def test_risk_mapping_and_unknown_default():
    assert risk_of("read_file") == "read"
    assert risk_of("write_file") == "write"
    assert risk_of("unknown_tool") == "execute"


def test_write_task_denied_by_default_gate(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    graph = build_graph(_mock_settings(), _registry())
    result = graph.invoke({"objective": "写入文件", "results": {}})

    assert result["tasks"][0]["id"] == "write_file"
    assert "拒绝" in result["results"]["write_file"]


def test_write_task_allowed_with_yes_gate(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    graph = build_graph(_mock_settings(), _registry(), gate=ConfirmationGate(confirm=yes_confirm))
    result = graph.invoke({"objective": "写入文件", "results": {}})

    assert "已写入" in result["results"]["write_file"]
    assert (tmp_path / "demo_output.txt").exists()
