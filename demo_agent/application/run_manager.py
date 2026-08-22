from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from demo_agent.adapters.mock_agent import MockAgent
from demo_agent.adapters.sqlite_repository import SqliteRepository
from demo_agent.domain.models import AgentTask, Message, Run, RunStatus, TaskStatus, new_id
from demo_agent.protocol import ProtocolError, event

Emit = Callable[[dict[str, Any]], Awaitable[None]]


class RunManager:
    def __init__(self, repository: SqliteRepository, agent: MockAgent, emit: Emit, approval_timeout: float = 120.0) -> None:
        self.repository = repository
        self.agent = agent
        self.emit = emit
        self.approval_timeout = approval_timeout
        self._jobs: dict[str, asyncio.Task[None]] = {}
        self._session_runs: dict[str, str] = {}
        self._approvals: dict[str, tuple[asyncio.Future[bool], str]] = {}

    def active_run(self, session_id: str) -> str | None:
        return self._session_runs.get(session_id)

    async def start(self, session_id: str, objective: str, attachments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if session_id in self._session_runs:
            raise ProtocolError("run_conflict", "this session already has an active run", {"run_id": self._session_runs[session_id]})
        # Verify existence before writing related records.
        self.repository.get_session(session_id)
        run = Run(new_id("run"), session_id, objective)
        message = Message(new_id("msg"), session_id, "user", objective, run_id=run.id)
        normalized_attachments = self._normalize_attachments(attachments or [])
        self.repository.add_run(run)
        stored_message = self.repository.add_message(message, normalized_attachments)
        await self.emit(event("message.created", {"message": stored_message}, session_id=session_id, run_id=run.id))
        self._session_runs[session_id] = run.id
        self._jobs[run.id] = asyncio.create_task(self._execute(run))
        return {**run.to_dict(), "message": {**message.to_dict(), "attachments": normalized_attachments}}

    @staticmethod
    def _normalize_attachments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in items:
            path = item.get("path")
            if not isinstance(path, str) or not path:
                raise ProtocolError("invalid_params", "attachment path is required")
            normalized.append({
                "id": str(item.get("id") or new_id("att")),
                "path": path,
                "name": str(item.get("name") or path.replace("\\", "/").rsplit("/", 1)[-1]),
                "size": item.get("size"),
                "mime_type": item.get("mime_type"),
            })
        return normalized

    async def _execute(self, run: Run) -> None:
        assistant_id = new_id("msg")
        try:
            self.repository.update_run(run.id, RunStatus.RUNNING)
            await self.emit(event("run.started", {"objective": run.objective}, session_id=run.session_id, run_id=run.id))
            raw_tasks = await self.agent.plan(run.objective)
            key_to_id = {str(item["key"]): new_id("task") for item in raw_tasks}
            tasks = [
                AgentTask(
                    id=key_to_id[str(item["key"])], run_id=run.id, session_id=run.session_id,
                    parent_id=key_to_id.get(str(item["parent_key"])) if item.get("parent_key") else None,
                    description=str(item["description"]), effort=str(item["effort"]), position=index,
                )
                for index, item in enumerate(raw_tasks)
            ]
            self.repository.add_tasks(tasks)
            await self.emit(event("plan.created", {"tasks": [task.to_dict() for task in tasks]}, session_id=run.session_id, run_id=run.id))
            for task in tasks:
                await self.emit(event("task.created", {"task": task.to_dict()}, session_id=run.session_id, run_id=run.id))

            # Execute each dependency-ready layer concurrently. Children wait for their parent.
            pending = {task.id: task for task in tasks}
            completed: set[str] = set()
            output_by_id: dict[str, str] = {}
            while pending:
                ready = [task for task in pending.values() if task.parent_id is None or task.parent_id in completed]
                if not ready:
                    raise RuntimeError("task graph contains an unresolved dependency cycle")
                results = await asyncio.gather(
                    *(self._execute_task(run, task) for task in ready), return_exceptions=True
                )
                first_error = next((result for result in results if isinstance(result, Exception)), None)
                if first_error is not None:
                    raise first_error
                for task, output in zip(ready, results, strict=True):
                    assert isinstance(output, str)
                    output_by_id[task.id] = output
                    completed.add(task.id)
                    pending.pop(task.id)

            outputs = [output_by_id[task.id] for task in tasks]

            report = self.agent.report(run.objective, outputs)
            message = Message(assistant_id, run.session_id, "assistant", report, run_id=run.id)
            self.repository.add_message(message)
            await self.emit(event("message.created", {"message": {**message.to_dict(), "content": "", "status": "streaming"}}, session_id=run.session_id, run_id=run.id))
            await self.emit(event("message.delta", {"message_id": assistant_id, "delta": report}, session_id=run.session_id, run_id=run.id))
            await self.emit(event("message.completed", {"message": message.to_dict()}, session_id=run.session_id, run_id=run.id))
            self.repository.update_run(run.id, RunStatus.COMPLETED)
            self._release(run)
            await self.emit(event("run.completed", {"report": report}, session_id=run.session_id, run_id=run.id))
        except asyncio.CancelledError:
            self.repository.update_run(run.id, RunStatus.CANCELLED)
            self._cancel_incomplete_tasks(run.id)
            self._release(run)
            await self.emit(event("run.cancelled", {}, session_id=run.session_id, run_id=run.id))
        except Exception as exc:
            message = exc.message if isinstance(exc, ProtocolError) else str(exc)
            self.repository.update_run(run.id, RunStatus.FAILED, message)
            failed_task_ids = self._fail_incomplete_tasks(run.id, message)
            error_message = Message(
                new_id("msg"), run.session_id, "system", f"运行失败：{message}",
                status="failed", run_id=run.id,
            )
            stored_error_message = self.repository.add_message(error_message)
            self._release(run)
            for task_id in failed_task_ids:
                await self.emit(event(
                    "task.failed", {"task_id": task_id, "error": message},
                    session_id=run.session_id, run_id=run.id,
                ))
            await self.emit(event(
                "message.created", {"message": stored_error_message},
                session_id=run.session_id, run_id=run.id,
            ))
            await self.emit(event(
                "message.completed", {"message": stored_error_message},
                session_id=run.session_id, run_id=run.id,
            ))
            await self.emit(event("run.failed", {"error": message}, session_id=run.session_id, run_id=run.id))
        finally:
            self._release(run)

    async def _execute_task(self, run: Run, task: AgentTask) -> str:
        if "[confirm]" in run.objective and task.position == 1:
            approved = await self._wait_for_approval(run, task)
            if not approved:
                raise ProtocolError("approval_rejected", "operation rejected by user")
        self.repository.update_task(task.id, TaskStatus.RUNNING)
        await self.emit(event("task.started", {"task_id": task.id}, session_id=run.session_id, run_id=run.id))
        output = await self.agent.execute(task.description, run.objective)
        midpoint = max(1, len(output) // 2)
        for delta in (output[:midpoint], output[midpoint:]):
            if delta:
                await self.emit(event("task.delta", {"task_id": task.id, "delta": delta}, session_id=run.session_id, run_id=run.id))
        self.repository.update_task(task.id, TaskStatus.COMPLETED, output=output)
        await self.emit(event("task.completed", {"task_id": task.id, "output": output}, session_id=run.session_id, run_id=run.id))
        return output

    def _release(self, run: Run) -> None:
        self._session_runs.pop(run.session_id, None)
        self._jobs.pop(run.id, None)
        for request_id, (future, approval_run_id) in list(self._approvals.items()):
            if not future.done() and approval_run_id == run.id:
                future.cancel()
                self._approvals.pop(request_id, None)

    async def _wait_for_approval(self, run: Run, task: AgentTask) -> bool:
        request_id = new_id("approval")
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._approvals[request_id] = (future, run.id)
        self.repository.update_run(run.id, RunStatus.WAITING)
        self.repository.update_task(task.id, TaskStatus.WAITING)
        await self.emit(event("approval.requested", {
            "request_id": request_id, "task_id": task.id,
            "action": task.description, "risk": "mock sensitive operation",
        }, session_id=run.session_id, run_id=run.id))
        try:
            approved = await asyncio.wait_for(future, self.approval_timeout)
        except TimeoutError as exc:
            raise ProtocolError("approval_timeout", "approval request timed out") from exc
        finally:
            self._approvals.pop(request_id, None)
        self.repository.update_run(run.id, RunStatus.RUNNING)
        await self.emit(event("approval.resolved", {"request_id": request_id, "approved": approved}, session_id=run.session_id, run_id=run.id))
        return approved

    async def resolve_approval(self, request_id: str, approved: bool) -> dict[str, Any]:
        approval = self._approvals.get(request_id)
        if approval is None or approval[0].done():
            raise ProtocolError("not_found", "approval request not found")
        future = approval[0]
        future.set_result(approved)
        return {"request_id": request_id, "approved": approved}

    async def cancel(self, run_id: str) -> dict[str, Any]:
        job = self._jobs.get(run_id)
        if job is None or job.done():
            raise ProtocolError("run_not_active", "run is not active")
        job.cancel()
        try:
            await job
        except asyncio.CancelledError:
            pass
        return self.repository.get_run(run_id)

    async def retry(self, run_id: str, task_id: str | None = None) -> dict[str, Any]:
        previous = self.repository.get_run(run_id)
        if previous["status"] not in {"failed", "cancelled"}:
            raise ProtocolError("invalid_state", "only failed or cancelled runs can be retried")
        objective = previous["objective"]
        if "[fail]" in objective:
            objective = objective.replace("[fail]", "").strip()
        if task_id is not None and not any(task["id"] == task_id for task in previous["tasks"]):
            raise ProtocolError("not_found", "task not found in run")
        result = await self.start(previous["session_id"], objective)
        result["retry_of_run_id"] = run_id
        result["retry_of_task_id"] = task_id
        return result

    def _cancel_incomplete_tasks(self, run_id: str) -> None:
        for task in self.repository.get_run(run_id)["tasks"]:
            if task["status"] not in {"completed", "failed"}:
                self.repository.update_task(task["id"], TaskStatus.CANCELLED)

    def _fail_incomplete_tasks(self, run_id: str, error: str) -> list[str]:
        failed_task_ids: list[str] = []
        for task in self.repository.get_run(run_id)["tasks"]:
            if task["status"] not in {"completed", "failed", "cancelled"}:
                self.repository.update_task(task["id"], TaskStatus.FAILED, error=error)
                failed_task_ids.append(task["id"])
        return failed_task_ids

    async def close(self) -> None:
        jobs = list(self._jobs.values())
        for job in jobs:
            job.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
