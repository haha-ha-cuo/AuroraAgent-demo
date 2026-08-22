from __future__ import annotations

import asyncio
import io
import json

from demo_agent.application.service import AgentService
from demo_agent.transport.stdio import serve_stdio
from demo_agent.transport.websocket import create_app


def test_stdio_uses_protocol_envelopes(tmp_path) -> None:
    service = AgentService(tmp_path / "stdio.db")
    stdin = io.StringIO(json.dumps({
        "protocol_version": 1, "request_id": "req_stdio", "method": "session.list", "params": {}
    }) + "\n")
    stdout = io.StringIO()
    asyncio.run(serve_stdio(service, stdin, stdout))
    records = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert records[0]["type"] == "runtime.ready"
    assert records[1]["request_id"] == "req_stdio"
    assert records[1]["ok"] is True


def test_websocket_app_exposes_health_and_ws(tmp_path) -> None:
    service = AgentService(tmp_path / "ws.db")
    app = create_app(service)
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/ws" in paths
