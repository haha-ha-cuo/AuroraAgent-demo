"""Compatibility exports for embedders using the previous server module."""

from demo_agent.application.service import AgentService
from demo_agent.transport.stdio import run_stdio, serve_stdio
from demo_agent.transport.websocket import create_app

__all__ = ["AgentService", "create_app", "run_stdio", "serve_stdio"]
