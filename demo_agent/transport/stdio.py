from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, TextIO

from demo_agent.application.service import AgentService


async def serve_stdio(service: AgentService, stdin: TextIO, stdout: TextIO) -> None:
    write_lock = asyncio.Lock()

    async def send(value: dict[str, Any]) -> None:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        async with write_lock:
            stdout.write(encoded + "\n")
            stdout.flush()

    remove_listener = service.add_listener(send)
    await send(await service.ready_event())
    pending: set[asyncio.Task[None]] = set()

    async def process(line: str) -> None:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = None
        await send(await service.handle(value))

    try:
        while True:
            line = await asyncio.to_thread(stdin.readline)
            if not line:
                break
            if not line.strip():
                continue
            task = asyncio.create_task(process(line))
            pending.add(task)
            task.add_done_callback(pending.discard)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    finally:
        remove_listener()
        await service.close()


def run_stdio(service: AgentService) -> None:
    asyncio.run(serve_stdio(service, sys.stdin, sys.stdout))
