from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from demo_agent.adapters.document_parser import LocalTextDocumentParser
from demo_agent.adapters.sqlite_repository import SqliteRepository
from demo_agent.domain.models import AgentTask, Message, Run, RunStatus, TaskStatus, new_id, utc_now
from demo_agent.protocol import ProtocolError, event

Emit = Callable[[dict[str, Any]], Awaitable[None]]
AgentFactory = Callable[[], Any]
logger = logging.getLogger(__name__)


class RunManager:
    def __init__(
        self,
        repository: SqliteRepository,
        agent_factory: AgentFactory,
        emit: Emit,
        approval_timeout: float = 120.0,
        document_parser: LocalTextDocumentParser | None = None,
    ) -> None:
        self.repository = repository
        self.agent_factory = agent_factory
        self.emit = emit
        self.approval_timeout = approval_timeout
        self.document_parser = document_parser or LocalTextDocumentParser()
        self._jobs: dict[str, asyncio.Task[None]] = {}
        self._session_runs: dict[str, str] = {}
        self._approvals: dict[str, tuple[asyncio.Future[bool], str]] = {}

    def active_run(self, session_id: str) -> str | None:
        return self._session_runs.get(session_id)

    async def start(
        self,
        session_id: str,
        objective: str,
        attachments: list[dict[str, Any]] | None = None,
        retry_of_run_id: str | None = None,
        retry_task_id: str | None = None,
    ) -> dict[str, Any]:
        if session_id in self._session_runs:
            raise ProtocolError("run_conflict", "this session already has an active run", {"run_id": self._session_runs[session_id]})
        snapshot = self.repository.get_session(session_id)
        normalized = self._normalize_attachments(attachments or [])
        documents = await self.document_parser.parse_many(normalized)
        history = self._history(snapshot)
        run = Run(new_id("run"), session_id, objective, retry_of_run_id=retry_of_run_id, retry_task_id=retry_task_id)
        message = Message(new_id("msg"), session_id, "user", objective, run_id=run.id)
        result = self.repository.create_run_with_message(run, message, normalized)
        await self.emit(event("message.created", {"message": result["message"]}, session_id=session_id, run_id=run.id))
        self._session_runs[session_id] = run.id
        self._jobs[run.id] = asyncio.create_task(self._execute(run, history, documents))
        return result

    @staticmethod
    def _normalize_attachments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        ids: set[str] = set()
        for item in items:
            path = item.get("path")
            if not isinstance(path, str) or not path:
                raise ProtocolError("invalid_params", "attachment path is required")
            attachment_id = str(item.get("id") or new_id("att"))
            if attachment_id in ids:
                raise ProtocolError("invalid_params", "attachment ids must be unique")
            ids.add(attachment_id)
            normalized.append(
                {
                    "id": attachment_id,
                    "path": path,
                    "name": str(item.get("name") or path.replace("\\", "/").rsplit("/", 1)[-1]),
                    "size": item.get("size"),
                    "media_type": item.get("media_type") or item.get("mime_type"),
                }
            )
        return normalized

    @staticmethod
    def _history(snapshot: dict[str, Any]) -> list[dict[str, str]]:
        messages = [
            {"role": item["role"], "content": item["content"]}
            for item in snapshot["messages"]
            if item["role"] in {"user", "assistant", "system"} and item["status"] == "completed"
        ]
        return messages[-20:]

    async def _execute(self, run: Run, history: list[dict[str, str]], documents: str) -> None:
        assistant_id = new_id("msg")
        assistant_created = False
        try:
            agent = self.agent_factory()
            self.repository.update_run(run.id, RunStatus.RUNNING)
            await self.emit(event("run.started", {"run": {**run.to_dict(), "status": "running"}}, session_id=run.session_id, run_id=run.id))
            raw_tasks = await agent.plan(run.objective, history, documents)
            tasks = self._build_tasks(run, raw_tasks)
            self.repository.add_tasks(tasks)
            await self.emit(event("plan.created", {"tasks": [task.to_dict() for task in tasks]}, session_id=run.session_id, run_id=run.id))
            for task in tasks:
                await self.emit(event("task.created", {"task": task.to_dict()}, session_id=run.session_id, run_id=run.id))
            outputs = await self._run_tasks(agent, run, tasks, history, documents)
            message = Message(assistant_id, run.session_id, "assistant", "", status="streaming", run_id=run.id)
            stored = self.repository.add_message(message)
            assistant_created = True
            await self.emit(event("message.created", {"message": stored}, session_id=run.session_id, run_id=run.id))
            report = ""
            async for delta in agent.report_stream(run.objective, history, documents, outputs):
                report += delta
                await self.emit(event("message.delta", {"message_id": assistant_id, "delta": delta}, session_id=run.session_id, run_id=run.id))
            if not report.strip():
                raise ProtocolError("provider_response_invalid", "模型未返回最终答复")
            self.repository.update_message(assistant_id, content=report, status="completed")
            completed_message = {**message.to_dict(), "content": report, "status": "completed"}
            await self.emit(event("message.completed", {"message": completed_message}, session_id=run.session_id, run_id=run.id))
            self.repository.update_run(run.id, RunStatus.COMPLETED)
            await self.emit(
                event("run.completed", {"run": {**run.to_dict(), "status": "completed"}, "report": report}, session_id=run.session_id, run_id=run.id)
            )
        except asyncio.CancelledError:
            self.repository.update_run(run.id, RunStatus.CANCELLED)
            self._cancel_incomplete_tasks(run.id)
            await self.emit(event("run.cancelled", {"run": {**run.to_dict(), "status": "cancelled"}}, session_id=run.session_id, run_id=run.id))
        except Exception as exc:
            message = exc.message if isinstance(exc, ProtocolError) else str(exc)
            code = exc.code if isinstance(exc, ProtocolError) else type(exc).__name__
            logger.error("run %s failed [%s]: %s", run.id, code, message)
            if assistant_created:
                self.repository.update_message(assistant_id, status="failed")
            self.repository.update_run(run.id, RunStatus.FAILED, message)
            failed_task_ids = self._fail_incomplete_tasks(run.id, message)
            await self._emit_failure(run, message, failed_task_ids)
        finally:
            self._release(run)

    @staticmethod
    def _build_tasks(run: Run, raw_tasks: list[dict[str, Any]]) -> list[AgentTask]:
        key_to_id = {str(item["key"]): new_id("task") for item in raw_tasks}
        return [
            AgentTask(
                id=key_to_id[str(item["key"])],
                run_id=run.id,
                session_id=run.session_id,
                parent_id=key_to_id.get(str(item["parent_key"])) if item.get("parent_key") else None,
                description=str(item["description"]),
                effort=str(item["effort"]),
                position=index,
            )
            for index, item in enumerate(raw_tasks)
        ]

    async def _run_tasks(self, agent: Any, run: Run, tasks: list[AgentTask], history: list[dict[str, str]], documents: str) -> list[str]:
        pending = {task.id: task for task in tasks}
        completed: set[str] = set()
        outputs: dict[str, str] = {}
        while pending:
            ready = [task for task in pending.values() if task.parent_id is None or task.parent_id in completed]
            if not ready:
                raise ProtocolError("provider_response_invalid", "task graph contains a dependency cycle")
            results = await asyncio.gather(
                *(self._execute_task(run, task, agent, history, documents, outputs.get(task.parent_id or "", "")) for task in ready),
                return_exceptions=True,
            )
            first_error = next((result for result in results if isinstance(result, Exception)), None)
            if first_error:
                raise first_error
            for task, output in zip(ready, results, strict=True):
                outputs[task.id] = str(output)
                completed.add(task.id)
                pending.pop(task.id)
        return [outputs[task.id] for task in tasks]

    async def _execute_task(
        self,
        run: Run,
        task: AgentTask,
        agent: Any,
        history: list[dict[str, str]],
        documents: str,
        parent_output: str,
    ) -> str:
        if "[confirm]" in run.objective and task.position == 1 and not await self._wait_for_approval(run, task):
            raise ProtocolError("approval_rejected", "operation rejected by user")
        self.repository.update_task(task.id, TaskStatus.RUNNING)
        await self.emit(event("task.started", {"task_id": task.id}, session_id=run.session_id, run_id=run.id))
        output = ""
        async for delta in agent.execute_stream(task.description, run.objective, history, documents, parent_output):
            output += delta
            await self.emit(event("task.delta", {"task_id": task.id, "delta": delta}, session_id=run.session_id, run_id=run.id))
        if not output.strip():
            raise ProtocolError("provider_response_invalid", "模型未返回任务结果")
        self.repository.update_task(task.id, TaskStatus.COMPLETED, output=output)
        await self.emit(event("task.completed", {"task_id": task.id, "output": output}, session_id=run.session_id, run_id=run.id))
        return output

    async def _wait_for_approval(self, run: Run, task: AgentTask) -> bool:
        request_id = new_id("approval")
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._approvals[request_id] = (future, run.id)
        expires_at = (datetime.now(UTC) + timedelta(seconds=self.approval_timeout)).isoformat()
        approval = {
            "id": request_id,
            "run_id": run.id,
            "session_id": run.session_id,
            "task_id": task.id,
            "action": task.description,
            "risk": "mock sensitive operation",
            "status": "pending",
            "approved": None,
            "expires_at": expires_at,
            "created_at": utc_now(),
            "resolved_at": None,
        }
        self.repository.add_approval(approval)
        self.repository.update_run(run.id, RunStatus.WAITING)
        self.repository.update_task(task.id, TaskStatus.WAITING)
        await self.emit(
            event("approval.requested", {"approval_id": request_id, "request_id": request_id, **approval}, session_id=run.session_id, run_id=run.id)
        )
        try:
            approved = await asyncio.wait_for(future, self.approval_timeout)
        except asyncio.CancelledError:
            self.repository.resolve_approval(request_id, "expired", None)
            raise
        except TimeoutError as exc:
            self.repository.resolve_approval(request_id, "expired", None)
            raise ProtocolError("approval_timeout", "approval request timed out") from exc
        finally:
            self._approvals.pop(request_id, None)
        status = "approved" if approved else "rejected"
        self.repository.resolve_approval(request_id, status, approved)
        self.repository.update_run(run.id, RunStatus.RUNNING)
        await self.emit(
            event(
                "approval.resolved",
                {"approval_id": request_id, "request_id": request_id, "approved": approved, "status": status},
                session_id=run.session_id,
                run_id=run.id,
            )
        )
        return approved

    async def resolve_approval(self, request_id: str, approved: bool) -> dict[str, Any]:
        approval = self._approvals.get(request_id)
        if approval is None or approval[0].done():
            raise ProtocolError("not_found", "approval request not found")
        approval[0].set_result(approved)
        return {"request_id": request_id, "approved": approved}

    async def cancel(self, run_id: str) -> dict[str, Any]:
        job = self._jobs.get(run_id)
        if job is None or job.done():
            raise ProtocolError("run_not_active", "run is not active")
        job.cancel()
        with suppress(asyncio.CancelledError):
            await job
        return self.repository.get_run(run_id)

    async def retry(self, run_id: str, task_id: str | None = None) -> dict[str, Any]:
        previous = self.repository.get_run(run_id)
        if previous["status"] not in {"failed", "cancelled"}:
            raise ProtocolError("invalid_state", "only failed or cancelled runs can be retried")
        objective = previous["objective"].replace("[fail]", "").strip()
        if task_id is not None and not any(task["id"] == task_id for task in previous["tasks"]):
            raise ProtocolError("not_found", "task not found in run")
        attachments = [{**item, "id": new_id("att")} for item in self.repository.get_run_attachments(run_id)]
        return await self.start(previous["session_id"], objective, attachments, run_id, task_id)

    async def _emit_failure(self, run: Run, message: str, task_ids: list[str]) -> None:
        error_message = Message(new_id("msg"), run.session_id, "system", f"运行失败：{message}", status="failed", run_id=run.id)
        stored = self.repository.add_message(error_message)
        for task_id in task_ids:
            await self.emit(event("task.failed", {"task_id": task_id, "error": message}, session_id=run.session_id, run_id=run.id))
        await self.emit(event("message.created", {"message": stored}, session_id=run.session_id, run_id=run.id))
        await self.emit(event("message.completed", {"message": stored}, session_id=run.session_id, run_id=run.id))
        await self.emit(
            event("run.failed", {"run": {**run.to_dict(), "status": "failed", "error": message}, "error": message}, session_id=run.session_id, run_id=run.id)
        )

    def _release(self, run: Run) -> None:
        self._session_runs.pop(run.session_id, None)
        self._jobs.pop(run.id, None)
        for request_id, (future, approval_run_id) in list(self._approvals.items()):
            if approval_run_id == run.id:
                if not future.done():
                    future.cancel()
                with suppress(ProtocolError):
                    self.repository.resolve_approval(request_id, "expired", None)
                self._approvals.pop(request_id, None)

    def _cancel_incomplete_tasks(self, run_id: str) -> None:
        for task in self.repository.get_run(run_id)["tasks"]:
            if task["status"] not in {"completed", "failed"}:
                self.repository.update_task(task["id"], TaskStatus.CANCELLED)

    def _fail_incomplete_tasks(self, run_id: str, error: str) -> list[str]:
        failed: list[str] = []
        for task in self.repository.get_run(run_id)["tasks"]:
            if task["status"] not in {"completed", "failed", "cancelled"}:
                self.repository.update_task(task["id"], TaskStatus.FAILED, error=error)
                failed.append(task["id"])
        return failed

    async def close(self) -> None:
        jobs = list(self._jobs.values())
        for job in jobs:
            job.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
