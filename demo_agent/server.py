"""FastAPI + WebSocket 服务：把 Agent 运行时暴露给桌面 UI。

协议（JSON）：
  UI → server: {"type":"run","objective":"..."}
               {"type":"confirm","request_id":"...","approved":true|false}
  server → UI: {"type":"hello","mode","model"}
               {"type":"run_start","objective"}
               {"type":"plan","tasks":[...]}
               {"type":"task_start","task_id","description","effort"}
               {"type":"token","task_id","text"}
               {"type":"task_result","task_id","result"}
               {"type":"report","report"}
               {"type":"done"}
               {"type":"error","message"}
               {"type":"confirm_request","request_id","action","risk"}

运行：``uv run python -m demo_agent.server [--port 8765]``
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Callable

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .capabilities import CapabilityRegistry
from .gate import ConfirmationGate
from .graph import build_graph
from .settings import Settings
from .tools import DEFAULT_TOOLS

DEFAULT_PORT = 8765


class DeferredConfirmationGate:
    """阻塞式确认门：把确认请求发给 UI，阻塞等待回复（带超时）。

    与 ``demo_agent.gate.ConfirmationGate`` 同接口，但 read 自动放行、
    write/execute 通过 ``emit`` 发出 confirm_request 后阻塞，直到 ``respond``。
    """

    def __init__(self, emit: Callable[[dict], None], timeout: float = 300.0):
        self._emit = emit
        self._timeout = timeout
        self._lock = threading.Lock()
        self._pending: dict[str, tuple[threading.Event, list]] = {}
        self._seq = 0

    def request(self, action: str, risk: str) -> bool:
        if risk == "read":
            return True
        with self._lock:
            self._seq += 1
            request_id = f"c{self._seq}"
            event = threading.Event()
            box: list = [False]
            self._pending[request_id] = (event, box)
        self._emit(
            {"type": "confirm_request", "request_id": request_id, "action": action, "risk": risk}
        )
        event.wait(self._timeout)
        with self._lock:
            self._pending.pop(request_id, None)
        return box[0]

    def respond(self, request_id: str, approved: bool) -> None:
        with self._lock:
            entry = self._pending.get(request_id)
        if entry is not None:
            event, box = entry
            box[0] = bool(approved)
            event.set()


def _default_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry(name="demo")
    reg.with_context("你正在用户的本地项目中工作，返回结果使用简体中文。")
    reg.with_context("写/执行操作会经确认门，未授权会被拒绝。")
    for tool in DEFAULT_TOOLS:
        reg.with_tool(tool)
    return reg


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="demo-agent runtime")

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        loop = asyncio.get_running_loop()
        outbox: asyncio.Queue = asyncio.Queue()

        def emit(event: dict) -> None:
            loop.call_soon_threadsafe(outbox.put_nowait, event)

        gate = DeferredConfirmationGate(emit)
        registry = _default_registry()

        async def send_outbox() -> None:
            while True:
                event = await outbox.get()
                await ws.send_json(event)

        async def receive_loop() -> None:
            await ws.send_json({"type": "hello", "mode": settings.mode, "model": settings.model})
            tasks: set = set()
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "invalid json"})
                    continue
                mtype = msg.get("type")
                if mtype == "run":
                    objective = str(msg.get("objective", ""))
                    task = asyncio.create_task(
                        _run_agent(objective, settings, registry, gate, emit)
                    )
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                elif mtype == "confirm":
                    gate.respond(
                        str(msg.get("request_id", "")), bool(msg.get("approved", False))
                    )

        sender = asyncio.create_task(send_outbox())
        try:
            await receive_loop()
        except WebSocketDisconnect:
            pass
        finally:
            sender.cancel()

    return app


async def _run_agent(
    objective: str,
    settings: Settings,
    registry: CapabilityRegistry,
    gate: DeferredConfirmationGate,
    emit: Callable[[dict], None],
) -> None:
    """在后台线程跑图，事件经 emit 回传。"""
    graph = build_graph(settings, registry, gate, on_event=emit)
    emit({"type": "run_start", "objective": objective})
    try:
        result = await asyncio.to_thread(
            graph.invoke, {"objective": objective, "results": {}}
        )
        emit({"type": "done"})
    except Exception as exc:  # noqa: BLE001
        emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="demo-agent runtime server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
