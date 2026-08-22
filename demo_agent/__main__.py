from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from demo_agent.application.service import AgentService
from demo_agent.transport.stdio import run_stdio
from demo_agent.transport.websocket import create_app


def _default_database_path() -> Path:
    configured = os.environ.get("AURORA_AGENT_DB")
    if configured:
        return Path(configured)
    return Path.home() / ".aurora-agent" / "runtime.sqlite3"


def main() -> None:
    parser = argparse.ArgumentParser(description="Aurora Agent local runtime")
    parser.add_argument("--stdio", action="store_true", help="serve NDJSON on stdin/stdout")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", type=Path, default=_default_database_path())
    arguments = parser.parse_args()
    service = AgentService(arguments.database)
    if arguments.stdio:
        run_stdio(service)
    else:
        uvicorn.run(create_app(service), host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
