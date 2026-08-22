from __future__ import annotations

import asyncio
from typing import Any

from demo_agent.application.service import AgentService


def request(method: str, params: dict[str, Any] | None = None, request_id: str = "req") -> dict[str, Any]:
    return {"protocol_version": 1, "request_id": request_id, "method": method, "params": params or {}}


async def wait_for(events: list[dict[str, Any]], event_type: str, count: int = 1) -> list[dict[str, Any]]:
    for _ in range(300):
        found = [item for item in events if item["type"] == event_type]
        if len(found) >= count:
            return found
        await asyncio.sleep(0.01)
    raise AssertionError(f"timed out waiting for {event_type}")


def test_continuous_conversation_and_recursive_tree(tmp_path) -> None:
    async def scenario() -> None:
        service = AgentService(tmp_path / "runtime.db", step_delay=0)
        events: list[dict[str, Any]] = []

        async def listener(value: dict[str, Any]) -> None:
            events.append(value)

        service.add_listener(listener)
        created = await service.handle(request("session.create", {"title": "Work"}))
        session_id = created["result"]["id"]
        first = await service.handle(request("run.start", {"session_id": session_id, "objective": "first"}))
        assert first["ok"]
        await wait_for(events, "run.completed")
        second = await service.handle(request("run.start", {"session_id": session_id, "objective": "second"}, "req2"))
        assert second["ok"]
        await wait_for(events, "run.completed", 2)
        session = (await service.handle(request("session.get", {"session_id": session_id})))["result"]
        assert [message["role"] for message in session["messages"]] == ["user", "assistant", "user", "assistant"]
        tasks = session["runs"][0]["tasks"]
        assert len(tasks) == 4
        assert any(task["parent_id"] is not None for task in tasks)
        assert all(task["status"] == "completed" for task in tasks)
        await service.close()

    asyncio.run(scenario())


def test_same_session_conflict_and_cross_session_concurrency(tmp_path) -> None:
    async def scenario() -> None:
        service = AgentService(tmp_path / "runtime.db", step_delay=0.05)
        first = (await service.handle(request("session.create", {"title": "A"})))["result"]["id"]
        second = (await service.handle(request("session.create", {"title": "B"}, "r2")))["result"]["id"]
        run_a = await service.handle(request("run.start", {"session_id": first, "objective": "A"}))
        conflict = await service.handle(request("run.start", {"session_id": first, "objective": "again"}, "c"))
        run_b = await service.handle(request("run.start", {"session_id": second, "objective": "B"}, "b"))
        assert run_a["ok"] and run_b["ok"]
        assert conflict["error"]["code"] == "run_conflict"
        assert service.run_manager.active_run(first) and service.run_manager.active_run(second)
        await service.close()

    asyncio.run(scenario())


def test_cancel_and_retry_failed_run(tmp_path) -> None:
    async def scenario() -> None:
        service = AgentService(tmp_path / "runtime.db", step_delay=0.05)
        events: list[dict[str, Any]] = []

        async def listener(value: dict[str, Any]) -> None:
            events.append(value)

        service.add_listener(listener)
        session_id = (await service.handle(request("session.create")))["result"]["id"]
        active = (await service.handle(request("run.start", {"session_id": session_id, "objective": "cancel me"})))["result"]
        await wait_for(events, "run.started")
        cancelled = await service.handle(request("run.cancel", {"run_id": active["id"]}))
        assert cancelled["result"]["status"] == "cancelled"

        failed = (await service.handle(request("run.start", {"session_id": session_id, "objective": "[fail] retry me"}, "f")))["result"]
        await wait_for(events, "run.failed")
        task_failures = [item for item in events if item["type"] == "task.failed" and item.get("run_id") == failed["id"]]
        assert task_failures
        assert all(item["payload"]["task_id"] and item["payload"]["error"] for item in task_failures)
        refreshed = (await service.handle(request("session.get", {"session_id": session_id})))["result"]
        persisted_error = [
            message for message in refreshed["messages"]
            if message["run_id"] == failed["id"] and message["role"] == "system"
        ]
        assert persisted_error[0]["status"] == "failed"
        assert "mock worker failure" in persisted_error[0]["content"]
        completed_error_events = [
            item for item in events
            if item["type"] == "message.completed"
            and item["payload"]["message"]["id"] == persisted_error[0]["id"]
        ]
        assert completed_error_events
        retried = await service.handle(request("run.retry", {"run_id": failed["id"]}, "retry"))
        assert retried["ok"] and retried["result"]["retry_of_run_id"] == failed["id"]
        await wait_for(events, "run.completed")
        await service.close()

    asyncio.run(scenario())


def test_approval_accept_and_timeout(tmp_path) -> None:
    async def scenario() -> None:
        service = AgentService(tmp_path / "runtime.db", step_delay=0, approval_timeout=0.05)
        events: list[dict[str, Any]] = []

        async def listener(value: dict[str, Any]) -> None:
            events.append(value)

        service.add_listener(listener)
        session_id = (await service.handle(request("session.create")))["result"]["id"]
        await service.handle(request("run.start", {"session_id": session_id, "objective": "[confirm] accepted"}))
        approval = (await wait_for(events, "approval.requested"))[0]
        resolved = await service.handle(request("approval.resolve", {"request_id": approval["payload"]["request_id"], "approved": True}))
        assert resolved["ok"]
        await wait_for(events, "run.completed")
        approved_snapshot = (await service.handle(request("session.get", {"session_id": session_id})))["result"]
        assert approved_snapshot["approvals"][0]["status"] == "approved"

        await service.handle(request("run.start", {"session_id": session_id, "objective": "[confirm] timeout"}, "timeout"))
        failed = await wait_for(events, "run.failed")
        assert "timed out" in failed[-1]["payload"]["error"]
        expired_snapshot = (await service.handle(request("session.get", {"session_id": session_id})))["result"]
        assert expired_snapshot["approvals"][-1]["status"] == "expired"
        await service.close()

    asyncio.run(scenario())


def test_service_validation_and_legacy_import(tmp_path) -> None:
    async def scenario() -> None:
        service = AgentService(tmp_path / "runtime.db")
        bad = await service.handle(request("run.start", {"objective": "missing session"}))
        assert bad["error"]["code"] == "invalid_params"
        imported = await service.handle(request("session.import_legacy", {
            "import_id": "browser-v1", "sessions": [{"id": "old", "title": "Old"}]
        }))
        assert imported["result"]["imported"] == 1
        assert (await service.handle(request("session.list")))["result"]["sessions"][0]["id"] == "old"
        await service.close()

    asyncio.run(scenario())
