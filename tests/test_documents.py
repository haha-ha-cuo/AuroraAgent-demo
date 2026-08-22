from __future__ import annotations

import asyncio

import pytest

from demo_agent.adapters.document_parser import LocalTextDocumentParser
from demo_agent.application.service import AgentService
from demo_agent.protocol import ProtocolError


def request(method: str, params: dict | None = None, request_id: str = "req") -> dict:
    return {"protocol_version": 1, "request_id": request_id, "method": method, "params": params or {}}


class CapturingAgent:
    def __init__(self) -> None:
        self.documents = ""
        self.history: list[dict[str, str]] = []
        self.parent_output = ""

    async def plan(self, objective, history, documents):
        self.documents = documents
        self.history = history
        return [
            {"key": "root", "parent_key": None, "description": "读取", "effort": "low"},
            {"key": "child", "parent_key": "root", "description": "总结", "effort": "medium"},
        ]

    async def execute_stream(self, description, objective, history, documents, parent_output):
        if description == "总结":
            self.parent_output = parent_output
        yield "FACT-42"

    async def report_stream(self, objective, history, documents, outputs):
        yield "总结："
        yield outputs[-1]


def test_document_parser_limits_and_errors(tmp_path) -> None:
    async def scenario() -> None:
        parser = LocalTextDocumentParser()
        valid = tmp_path / "facts.md"
        valid.write_text("事实是 FACT-42", encoding="utf-8")
        context = await parser.parse_many([{"path": str(valid), "name": valid.name}])
        assert "FACT-42" in context
        unsupported = tmp_path / "facts.json"
        unsupported.write_text("{}", encoding="utf-8")
        with pytest.raises(ProtocolError, match="unsupported") as unsupported_error:
            await parser.parse(unsupported)
        assert unsupported_error.value.code == "attachment_type_unsupported"
        invalid = tmp_path / "bad.txt"
        invalid.write_bytes(b"\xff")
        with pytest.raises(ProtocolError) as encoding_error:
            await parser.parse(invalid)
        assert encoding_error.value.code == "attachment_encoding_invalid"
        missing = tmp_path / "missing.md"
        with pytest.raises(ProtocolError) as missing_error:
            await parser.parse(missing)
        assert missing_error.value.code == "attachment_not_found"
        oversized = tmp_path / "large.md"
        oversized.write_bytes(b"x" * (parser.MAX_FILE_BYTES + 1))
        with pytest.raises(ProtocolError) as size_error:
            await parser.parse(oversized)
        assert size_error.value.code == "attachment_too_large"
        link = tmp_path / "link.md"
        try:
            link.symlink_to(valid)
        except OSError:
            return
        with pytest.raises(ProtocolError) as link_error:
            await parser.parse(link)
        assert link_error.value.code == "attachment_type_unsupported"

    asyncio.run(scenario())


def test_document_context_history_parent_output_and_atomic_validation(tmp_path) -> None:
    async def scenario() -> None:
        service = AgentService(tmp_path / "runtime.db", step_delay=0)
        agent = CapturingAgent()
        service.run_manager.agent_factory = lambda: agent
        events: list[dict] = []

        async def listener(value):
            events.append(value)

        service.add_listener(listener)
        session_id = (await service.handle(request("session.create")))["result"]["id"]
        document = tmp_path / "facts.md"
        document.write_text("事实是 FACT-42", encoding="utf-8")
        attachment = {"id": "a1", "path": str(document), "name": document.name, "media_type": "text/markdown"}
        started = await service.handle(request("run.start", {"session_id": session_id, "objective": "总结", "attachments": [attachment]}))
        assert started["ok"]
        for _ in range(200):
            if any(item["type"] == "run.completed" for item in events):
                break
            await asyncio.sleep(0.01)
        assert "FACT-42" in agent.documents
        assert agent.parent_output == "FACT-42"
        assert any(item["type"] == "message.delta" for item in events)
        duplicate = await service.handle(request("run.start", {"session_id": session_id, "objective": "again", "attachments": [attachment, attachment]}, "duplicate"))
        assert duplicate["error"]["code"] == "invalid_params"
        with service.repository._connect() as db:
            assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        await service.close()

    asyncio.run(scenario())


def test_openai_configuration_failure_is_explicit(tmp_path, monkeypatch) -> None:
    async def scenario() -> None:
        service = AgentService(tmp_path / "runtime.db", step_delay=0)
        monkeypatch.delenv("DEMO_AGENT_API_KEY", raising=False)
        monkeypatch.delenv("AGENT_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        service.repository.settings_update({"provider": "openai", "model": "test-model"})
        events: list[dict] = []

        async def listener(value):
            events.append(value)

        service.add_listener(listener)
        session_id = (await service.handle(request("session.create")))["result"]["id"]
        await service.handle(request("run.start", {"session_id": session_id, "objective": "test"}))
        for _ in range(200):
            if any(item["type"] == "run.failed" for item in events):
                break
            await asyncio.sleep(0.01)
        failed = next(item for item in events if item["type"] == "run.failed")
        assert "API Key" in failed["payload"]["error"]
        assert service.repository.get_session(session_id)["runs"][0]["status"] == "failed"
        await service.close()

    asyncio.run(scenario())


def test_retry_reloads_documents_with_new_attachment_ids(tmp_path) -> None:
    async def scenario() -> None:
        service = AgentService(tmp_path / "runtime.db", step_delay=0)
        events: list[dict] = []

        async def listener(value):
            events.append(value)

        service.add_listener(listener)
        session_id = (await service.handle(request("session.create")))["result"]["id"]
        document = tmp_path / "retry.md"
        document.write_text("RETRY-FACT", encoding="utf-8")
        started = await service.handle(
            request(
                "run.start",
                {
                    "session_id": session_id,
                    "objective": "[fail] summarize",
                    "attachments": [{"id": "original", "path": str(document), "name": document.name}],
                },
            )
        )
        run_id = started["result"]["id"]
        for _ in range(200):
            if any(item["type"] == "run.failed" and item.get("run_id") == run_id for item in events):
                break
            await asyncio.sleep(0.01)
        retried = await service.handle(request("run.retry", {"run_id": run_id}, "retry"))
        assert retried["ok"]
        assert retried["result"]["retry_of_run_id"] == run_id
        assert retried["result"]["message"]["attachments"][0]["id"] != "original"
        await service.close()

    asyncio.run(scenario())
