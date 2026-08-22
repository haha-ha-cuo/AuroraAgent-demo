from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Session:
    id: str
    title: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Message:
    id: str
    session_id: str
    role: str
    content: str
    status: str = "completed"
    run_id: str | None = None
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentTask:
    id: str
    run_id: str
    session_id: str
    parent_id: str | None
    description: str
    effort: str
    status: TaskStatus = TaskStatus.QUEUED
    output: str | None = None
    error: str | None = None
    position: int = 0

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = str(self.status)
        return value


@dataclass(slots=True)
class Run:
    id: str
    session_id: str
    objective: str
    status: RunStatus = RunStatus.QUEUED
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = str(self.status)
        return value
