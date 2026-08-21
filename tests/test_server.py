"""WebSocket 服务的端到端测试（mock 模式，无真实模型）。"""

from fastapi.testclient import TestClient

from demo_agent.server import create_app
from demo_agent.settings import Settings


def _mock_settings() -> Settings:
    return Settings(api_key=None, base_url="https://api.openai.com/v1", model="gpt-4o-mini")


def _collect(ws) -> list[dict]:
    events = []
    while True:
        ev = ws.receive_json()
        events.append(ev)
        if ev["type"] in ("done", "error"):
            return events


def test_hello_and_event_stream():
    app = create_app(_mock_settings())
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["mode"] == "mock"

        ws.send_json(
            {"type": "run", "objective": "列出项目文件结构，并阅读 README.md 总结项目定位"}
        )
        events = _collect(ws)

    types = [e["type"] for e in events]
    assert "run_start" in types
    assert "plan" in types
    assert "task_start" in types
    assert "task_result" in types
    assert "report" in types
    assert types[-1] == "done"

    plan = next(e for e in events if e["type"] == "plan")
    task_ids = {t["id"] for t in plan["tasks"]}
    assert "list_files" in task_ids
    assert "read_readme" in task_ids


def test_confirm_gate_denies_write():
    app = create_app(_mock_settings())
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # hello
        ws.send_json({"type": "run", "objective": "写入文件"})

        got_confirm = False
        events = []
        while True:
            ev = ws.receive_json()
            if ev["type"] == "confirm_request":
                got_confirm = True
                ws.send_json(
                    {"type": "confirm", "request_id": ev["request_id"], "approved": False}
                )
            events.append(ev)
            if ev["type"] in ("done", "error"):
                break

    assert got_confirm is True
    results = [e for e in events if e["type"] == "task_result"]
    assert any("拒绝" in r.get("result", "") for r in results)


def test_confirm_gate_approves_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app(_mock_settings())
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # hello
        ws.send_json({"type": "run", "objective": "写入文件"})

        events = []
        while True:
            ev = ws.receive_json()
            if ev["type"] == "confirm_request":
                ws.send_json(
                    {"type": "confirm", "request_id": ev["request_id"], "approved": True}
                )
            events.append(ev)
            if ev["type"] in ("done", "error"):
                break

    assert (tmp_path / "demo_output.txt").exists()
