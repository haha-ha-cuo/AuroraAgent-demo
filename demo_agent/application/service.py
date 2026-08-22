from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from demo_agent.adapters.mock_agent import MockAgent
from demo_agent.adapters.openai_agent import OpenAiAgent
from demo_agent.adapters.sqlite_repository import SqliteRepository
from demo_agent.application.run_manager import RunManager
from demo_agent.application.settings import api_key_configured, load_environment, resolve_settings
from demo_agent.domain.models import DEFAULT_PROJECT_ID, Project, Session, new_id, utc_now
from demo_agent.protocol import ProtocolError, event, parse_request, response_error, response_ok

EventListener = Callable[[dict[str, Any]], Awaitable[None]]


class AgentService:
    def __init__(self, database_path: str | Path, *, step_delay: float = 0.01, approval_timeout: float = 120.0) -> None:
        load_environment()
        self.repository = SqliteRepository(database_path)
        self.repository.recover_interrupted()
        self._listeners: set[EventListener] = set()
        self.step_delay = step_delay
        self.run_manager = RunManager(self.repository, self._create_agent, self._broadcast, approval_timeout=approval_timeout)
        self.started_at = utc_now()

    def _create_agent(self) -> Any:
        settings = resolve_settings(self.repository.settings_get())
        provider = settings["provider"].lower()
        if provider == "mock":
            return MockAgent(self.step_delay)
        if provider != "openai":
            raise ProtocolError("provider_unsupported", f"unsupported provider: {provider}")
        api_key = os.environ.get("DEMO_AGENT_API_KEY") or os.environ.get("AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ProtocolError("provider_not_configured", "OpenAI Provider 缺少 API Key，请在设置中配置")
        model = str(settings["model"]).strip()
        if not model:
            raise ProtocolError("provider_not_configured", "OpenAI Provider 缺少模型名称")
        return OpenAiAgent(model, api_key, str(settings["base_url"]))

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
            "project.list": self._handle_project_list,
            "project.get": self._handle_project_get,
            "project.create": self._handle_project_create,
            "project.rename": self._handle_project_rename,
            "project.delete": self._handle_project_delete,
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
        settings = resolve_settings(self.repository.settings_get())
        configured = api_key_configured()
        return {
            "connected": True,
            "mode": "mock" if settings["provider"] == "mock" else "openai",
            "provider": settings["provider"],
            "model": settings["model"],
            "api_key_configured": configured,
            "configuration_status": "ready" if settings["provider"] == "mock" or configured else "missing_api_key",
            "started_at": self.started_at,
            "database": self.repository.database_info(),
        }

    async def _handle_runtime_status(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._runtime_status()

    async def _handle_runtime_restart(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"restart_required": True, "status": await self._runtime_status()}

    async def _handle_project_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"projects": self.repository.list_projects()}

    async def _handle_project_get(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self.repository.get_project(self._required_string(params, "project_id"))
        sessions = [s for s in self.repository.list_sessions() if s.get("project_id") == project["id"]]
        return {**project, "sessions": sessions}

    async def _handle_project_create(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "新项目").strip()[:200] or "新项目"
        now = utc_now()
        project = Project(str(params.get("project_id") or new_id("project")), name, now, now)
        result = self.repository.create_project(project)
        await self._broadcast(event("project.updated", {"project": result}))
        return result

    async def _handle_project_rename(self, params: dict[str, Any]) -> dict[str, Any]:
        project_id = self._required_string(params, "project_id")
        name = self._required_string(params, "name")[:200]
        result = self.repository.rename_project(project_id, name)
        await self._broadcast(event("project.updated", {"project": result}))
        return result

    async def _handle_project_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        project_id = self._required_string(params, "project_id")
        if project_id == DEFAULT_PROJECT_ID:
            raise ProtocolError("invalid_state", "the default project cannot be deleted")
        sessions = [s for s in self.repository.list_sessions() if s.get("project_id") == project_id]
        if any(self.run_manager.active_run(s["id"]) for s in sessions):
            raise ProtocolError("run_conflict", "cancel active runs before deleting the project")
        self.repository.delete_project(project_id)
        await self._broadcast(event("project.updated", {"deleted": True, "project_id": project_id}))
        return {"project_id": project_id, "deleted": True}

    async def _handle_session_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"sessions": self.repository.list_sessions()}

    async def _handle_session_create(self, params: dict[str, Any]) -> dict[str, Any]:
        title = str(params.get("title") or "新对话").strip()[:200] or "新对话"
        project_id = params.get("project_id") or DEFAULT_PROJECT_ID
        if not isinstance(project_id, str):
            raise ProtocolError("invalid_params", "project_id must be a string")
        self.repository.get_project(project_id)
        now = utc_now()
        session = Session(str(params.get("session_id") or new_id("session")), title, now, now, project_id)
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
        return {**resolve_settings(self.repository.settings_get()), "api_key_configured": api_key_configured()}

    async def _handle_settings_update(self, params: dict[str, Any]) -> dict[str, Any]:
        if "api_key" in params or "apiKey" in params:
            raise ProtocolError("keychain_required", "API Key 只能由桌面应用写入系统钥匙串")
        public_values = {key: params[key] for key in ("provider", "base_url", "model") if key in params}
        if any(not isinstance(value, str) for value in public_values.values()):
            raise ProtocolError("invalid_params", "model settings must be strings")
        if "provider" in public_values and public_values["provider"] not in {"mock", "openai"}:
            raise ProtocolError("invalid_params", "provider must be mock or openai")
        stored = self.repository.settings_update(public_values)
        configured = params.get("api_key_configured")
        return {
            **resolve_settings(stored),
            "api_key_configured": configured if isinstance(configured, bool) else api_key_configured(),
            "restart_required": isinstance(configured, bool),
        }

    async def close(self) -> None:
        await self.run_manager.close()
