from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from demo_agent.application.service import AgentService


def create_app(service: AgentService) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await service.close()

    app = FastAPI(title="Aurora Agent Runtime", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return (await service.handle({"protocol_version": 1, "request_id": "health", "method": "runtime.status", "params": {}}))["result"]

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        send_lock = asyncio.Lock()

        async def send(value: dict[str, Any]) -> None:
            async with send_lock:
                await websocket.send_json(value)

        remove_listener = service.add_listener(send)
        await send(await service.ready_event())
        try:
            while True:
                request = await websocket.receive_json()
                await send(await service.handle(request))
        except WebSocketDisconnect:
            pass
        finally:
            remove_listener()

    return app
