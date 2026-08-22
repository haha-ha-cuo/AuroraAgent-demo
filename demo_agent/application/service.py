from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from demo_agent.adapters.mock_agent import MockAgent
from demo_agent.adapters.sqlite_repository import SqliteRepository
from demo_agent.application.run_manager import RunManager
from demo_agent.domain.models import Session, new_id, utc_now
from demo_agent.protocol import ProtocolError, event, parse_request, response_error, response_ok

EventListener = Callable[[dict[str, Any]], Awaitable[None]]


class AgentService:
    """Application boundary shared by stdio, WebSocket, tests and the desktop broker."""

    def __init__(self, database_path: str | Path, *, step_delay: float = 0.01, approval_timeout: float = 120.0) -> None:
        self.repository = SqliteRepository(database_path)
        self.repository.recover_interrupted()
        self._listeners: set[EventListener] = set()
        self.run_manager = RunManager(
            self.repository, MockAgent(step_delay), self._broadcast, approval_timeout=approval_timeout
        )
        self.started_at = utc_now()

    def add_listener(self, listener: EventListener) -> Callable[[], None]:
        self._listeners.add(listener)

        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    async def _broadcast(self, value: dict[str, Any]) -> None:
        listeners = list(self._listeners)
        if listeners:
            await asyncio.gather(*(listener(value) for listener in listeners), return_exceptions=True)

    async def ready_event(self) -> dict[str, Any]:
        return event("runtime.ready", await self._runtime_status())

    async def handle(self, raw_request: Any) -> dict[str, Any]:
        request_id = raw_request.get("request_id", "unknown") if isinstance(raw_request, dict) else "unknown"
        try:
            request = parse_request(raw_request)
            result = await self._dispatch(request["method"], request["params"])
            return response_ok(request["request_id"], result)
        except ProtocolError as exc:
            return response_error(str(request_id), exc)
        except Exception as exc:
            return response_error(str(request_id), ProtocolError("internal_error", str(exc)))

    async def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        handlers: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {
            "runtime.status": self._handle_runtime_status,
            "runtime.restart": self._handle_runtime_restart,
            "session.list": self._handle_session_list,
            "session.create": self._handle_session_create,
            "session.get": self._handle_session_get,
            "session.rename": self._handle_session_rename,
            "session.delete": self._handle_session_delete,
            "session.clear": self._handle_session_clear,
            "session.import_legacy": self._handle_session_import_legacy,
            "run.start": self._handle_run_start,
            "run.cancel": self._handle_run_cancel,
            "run.retry": self._handle_run_retry,
            "approval.resolve": self._handle_approval_resolve,
            "settings.get": self._handle_settings_get,
            "settings.update": self._handle_settings_update,
        }
        handler = handlers.get(method)
        if handler is None:
            raise ProtocolError("method_not_found", f"unknown method: {method}")
        return await handler(params)

    @staticmethod
    def _required_string(params: dict[str, Any], key: str) -> str:
        value = params.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ProtocolError("invalid_params", f"{key} is required")
        return value.strip()

    async def _runtime_status(self) -> dict[str, Any]:
        settings = self.repository.settings_get()
        return {
            "connected": True,
            "mode": "mock" if settings["provider"] == "mock" else "adapter_pending",
            "provider": settings["provider"],
            "model": settings["model"],
            "started_at": self.started_at,
            "database": self.repository.database_info(),
        }

    async def _handle_runtime_status(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._runtime_status()

    async def _handle_runtime_restart(self, params: dict[str, Any]) -> dict[str, Any]:
        # Process restart is owned by the Rust broker; Python confirms it is ready to be restarted.
        return {"restart_required": True, "status": await self._runtime_status()}

    async def _handle_session_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"sessions": self.repository.list_sessions()}

    async def _handle_session_create(self, params: dict[str, Any]) -> dict[str, Any]:
        title = str(params.get("title") or "新对话").strip()[:200] or "新对话"
        now = utc_now()
        session = Session(str(params.get("session_id") or new_id("session")), title, now, now)
        result = self.repository.create_session(session)
        await self._broadcast(event("session.updated", {"session": result}, session_id=session.id))
        return result

    async def _handle_session_get(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.repository.get_session(self._required_string(params, "session_id"))

    async def _handle_session_rename(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = self._required_string(params, "session_id")
        title = self._required_string(params, "title")[:200]
        result = self.repository.rename_session(session_id, title)
        await self._broadcast(event("session.updated", {"session": result}, session_id=session_id))
        return result

    async def _handle_session_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = self._required_string(params, "session_id")
        if self.run_manager.active_run(session_id):
            raise ProtocolError("run_conflict", "cancel the active run before deleting the session")
        self.repository.delete_session(session_id)
        await self._broadcast(event("session.updated", {"deleted": True}, session_id=session_id))
        return {"session_id": session_id, "deleted": True}

    async def _handle_session_clear(self, params: dict[str, Any]) -> dict[str, Any]:
        if any(self.run_manager.active_run(item["id"]) for item in self.repository.list_sessions()):
            raise ProtocolError("run_conflict", "cancel active runs before clearing history")
        return {"deleted": self.repository.clear_sessions()}

    async def _handle_session_import_legacy(self, params: dict[str, Any]) -> dict[str, Any]:
        import_id = self._required_string(params, "import_id")
        sessions = params.get("sessions")
        if not isinstance(sessions, list):
            raise ProtocolError("invalid_params", "sessions must be an array")
        return self.repository.import_legacy(import_id, sessions)

    async def _handle_run_start(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = self._required_string(params, "session_id")
        objective = self._required_string(params, "objective")
        attachments = params.get("attachments", [])
        if not isinstance(attachments, list) or not all(isinstance(item, dict) for item in attachments):
            raise ProtocolError("invalid_params", "attachments must be an array of objects")
        return await self.run_manager.start(session_id, objective, attachments)

    async def _handle_run_cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self.run_manager.cancel(self._required_string(params, "run_id"))

    async def _handle_run_retry(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = params.get("task_id")
        if task_id is not None and not isinstance(task_id, str):
            raise ProtocolError("invalid_params", "task_id must be a string")
        return await self.run_manager.retry(self._required_string(params, "run_id"), task_id)

    async def _handle_approval_resolve(self, params: dict[str, Any]) -> dict[str, Any]:
        approved = params.get("approved")
        if not isinstance(approved, bool):
            raise ProtocolError("invalid_params", "approved must be a boolean")
        return await self.run_manager.resolve_approval(self._required_string(params, "request_id"), approved)

    async def _handle_settings_get(self, params: dict[str, Any]) -> dict[str, Any]:
        return {**self.repository.settings_get(), "api_key_configured": False}

    async def _handle_settings_update(self, params: dict[str, Any]) -> dict[str, Any]:
        # api_key is intentionally not persisted or echoed. The Rust broker owns the system keychain.
        public_values = {key: params[key] for key in ("provider", "base_url", "model") if key in params}
        if any(not isinstance(value, str) for value in public_values.values()):
            raise ProtocolError("invalid_params", "model settings must be strings")
        return {**self.repository.settings_update(public_values), "api_key_configured": bool(params.get("api_key_configured", False))}

    async def close(self) -> None:
        await self.run_manager.close()
