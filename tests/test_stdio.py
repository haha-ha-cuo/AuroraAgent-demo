"""stdio 传输的端到端测试：以子进程方式跑 ``--stdio``，经 stdin/stdout 收发 NDJSON。"""

import json
import os
import subprocess
import sys


def _spawn(cwd=None) -> subprocess.Popen:
    """以 mock 模式拉起 ``--stdio`` 子进程（清空密钥，避免读取 .env）。"""
    env = {**os.environ, "AGENT_API_KEY": "", "OPENAI_API_KEY": ""}
    return subprocess.Popen(
        [sys.executable, "-m", "demo_agent.server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
    )


def _send(proc: subprocess.Popen, msg: dict) -> None:
    proc.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
    proc.stdin.flush()


def _recv(proc: subprocess.Popen) -> dict | None:
    line = proc.stdout.readline()
    if not line:
        return None
    return json.loads(line.decode("utf-8"))


def _collect(proc: subprocess.Popen, on_event=None) -> list[dict]:
    """读取事件直到 done/error，可选在 confirm_request 上回调。"""
    events = []
    while True:
        ev = _recv(proc)
        assert ev is not None, "子进程 stdout 提前 EOF"
        if on_event is not None:
            on_event(ev)
        events.append(ev)
        if ev["type"] in ("done", "error"):
            return events


def test_stdio_hello_and_event_stream():
    proc = _spawn()
    try:
        hello = _recv(proc)
        assert hello["type"] == "hello"
        assert hello["mode"] == "mock"

        _send(proc, {"type": "run", "objective": "列出项目文件结构，并阅读 README.md 总结项目定位"})
        events = _collect(proc)
    finally:
        proc.stdin.close()
        proc.wait(timeout=15)

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


def test_stdio_confirm_gate_denies_write(tmp_path):
    proc = _spawn(cwd=str(tmp_path))
    try:
        assert _recv(proc)["type"] == "hello"
        _send(proc, {"type": "run", "objective": "写入文件"})

        got_confirm = False

        def deny(ev: dict) -> None:
            nonlocal got_confirm
            if ev["type"] == "confirm_request":
                got_confirm = True
                _send(proc, {"type": "confirm", "request_id": ev["request_id"], "approved": False})

        events = _collect(proc, on_event=deny)
    finally:
        proc.stdin.close()
        proc.wait(timeout=15)

    assert got_confirm is True
    results = [e for e in events if e["type"] == "task_result"]
    assert any("拒绝" in r.get("result", "") for r in results)
    assert not (tmp_path / "demo_output.txt").exists()


def test_stdio_confirm_gate_approves_write(tmp_path):
    proc = _spawn(cwd=str(tmp_path))
    try:
        assert _recv(proc)["type"] == "hello"
        _send(proc, {"type": "run", "objective": "写入文件"})

        def approve(ev: dict) -> None:
            if ev["type"] == "confirm_request":
                _send(proc, {"type": "confirm", "request_id": ev["request_id"], "approved": True})

        _collect(proc, on_event=approve)
    finally:
        proc.stdin.close()
        proc.wait(timeout=15)

    assert (tmp_path / "demo_output.txt").exists()
