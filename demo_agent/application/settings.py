from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

DEFAULT_PROVIDER = "mock"
DEFAULT_MODEL = "mock-agent-v1"
DEFAULTS = {"provider": DEFAULT_PROVIDER, "base_url": "", "model": DEFAULT_MODEL}

ENV_KEYS = {
    "provider": "AGENT_PROVIDER",
    "base_url": "AGENT_BASE_URL",
    "model": "AGENT_MODEL",
}


def load_environment() -> None:
    load_dotenv()


def api_key_configured() -> bool:
    return bool(os.environ.get("DEMO_AGENT_API_KEY") or os.environ.get("AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def env_defaults() -> dict[str, Any]:
    values = dict(DEFAULTS)
    for key, env in ENV_KEYS.items():
        raw = os.environ.get(env)
        if raw:
            values[key] = raw
    return values


def resolve_settings(stored: dict[str, Any]) -> dict[str, Any]:
    values = env_defaults()
    for key in ("provider", "base_url", "model"):
        if stored.get(key):
            values[key] = stored[key]
    return values
