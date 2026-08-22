from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from demo_agent.adapters.sqlite_maintenance import database_info, import_legacy, recover_interrupted
from demo_agent.adapters.sqlite_schema import MIGRATION_V1_TO_V2, MIGRATION_V2_TO_V3, SCHEMA_V3
from demo_agent.domain.models import (
    DEFAULT_PROJECT_ID,
    DEFAULT_PROJECT_NAME,
    AgentTask,
    Message,
    Project,
    Run,
    RunStatus,
    Session,
    TaskStatus,
    utc_now,
)
from demo_agent.protocol import ProtocolError


class SqliteRepository:
    SCHEMA_VERSION = 3

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _migrate(self) -> None:
        db = self._connect()
        try:
            db.execute("PRAGMA journal_mode = WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > self.SCHEMA_VERSION:
                raise RuntimeError(f"database version {version} is newer than supported")
            if version == self.SCHEMA_VERSION:
                return
            scripts = {0: SCHEMA_V3, 1: MIGRATION_V1_TO_V2 + MIGRATION_V2_TO_V3, 2: MIGRATION_V2_TO_V3}
            db.execute("PRAGMA foreign_keys = OFF")
            db.executescript("BEGIN IMMEDIATE;\n" + scripts[version])
            if version == 0:
                self._seed_default_project(db)
            violations = db.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError("database migration failed foreign key validation")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _seed_default_project(db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO projects(id,name,created_at,updated_at) VALUES(?,?,?,?)",
            (DEFAULT_PROJECT_ID, DEFAULT_PROJECT_NAME, utc_now(), utc_now()),
        )

    def create_project(self, project: Project) -> dict[str, Any]:
        with self.transaction() as db:
            db.execute(
                "INSERT INTO projects(id,name,created_at,updated_at) VALUES(?,?,?,?)",
                (project.id, project.name, project.created_at, project.updated_at),
            )
        return project.to_dict()

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM projects ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None:
                raise ProtocolError("not_found", "project not found")
        return dict(row)

    def rename_project(self, project_id: str, name: str) -> dict[str, Any]:
        now = utc_now()
        with self.transaction() as db:
            changed = db.execute("UPDATE projects SET name=?,updated_at=? WHERE id=?", (name, now, project_id)).rowcount
            if not changed:
                raise ProtocolError("not_found", "project not found")
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> None:
        with self.transaction() as db:
            changed = db.execute("DELETE FROM projects WHERE id=?", (project_id,)).rowcount
            if not changed:
                raise ProtocolError("not_found", "project not found")

    def create_session(self, session: Session) -> dict[str, Any]:
        with self.transaction() as db:
            db.execute(
                "INSERT INTO sessions(id,title,project_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                (session.id, session.title, session.project_id, session.created_at, session.updated_at),
            )
        return session.to_dict()

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT s.*, (SELECT status FROM runs r WHERE r.session_id=s.id ORDER BY created_at DESC LIMIT 1) status
                   FROM sessions s ORDER BY updated_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._connect() as db:
            session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if session is None:
                raise ProtocolError("not_found", "session not found", {"session_id": session_id})
            messages = [dict(row) for row in db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY created_at", (session_id,))]
            for message in messages:
                message["attachments"] = [dict(row) for row in db.execute("SELECT * FROM attachments WHERE message_id=?", (message["id"],))]
            runs = [dict(row) for row in db.execute("SELECT * FROM runs WHERE session_id=? ORDER BY created_at", (session_id,))]
            for run in runs:
                run["tasks"] = [dict(row) for row in db.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY position", (run["id"],))]
            approvals = [dict(row) for row in db.execute("SELECT * FROM approvals WHERE session_id=? ORDER BY created_at", (session_id,))]
        status = runs[-1]["status"] if runs else "idle"
        return {**dict(session), "status": status, "messages": messages, "runs": runs, "approvals": approvals}

    def rename_session(self, session_id: str, title: str) -> dict[str, Any]:
        now = utc_now()
        with self.transaction() as db:
            changed = db.execute("UPDATE sessions SET title=?,updated_at=? WHERE id=?", (title, now, session_id)).rowcount
            if not changed:
                raise ProtocolError("not_found", "session not found")
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> None:
        with self.transaction() as db:
            changed = db.execute("DELETE FROM sessions WHERE id=?", (session_id,)).rowcount
            if not changed:
                raise ProtocolError("not_found", "session not found")

    def clear_sessions(self) -> int:
        with self.transaction() as db:
            count = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            db.execute("DELETE FROM sessions")
        return count

    def add_message(self, message: Message, attachments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        with self.transaction() as db:
            self._insert_message(db, message, attachments or [])
        value = message.to_dict()
        value["attachments"] = attachments or []
        return value

    @staticmethod
    def _insert_message(db: sqlite3.Connection, message: Message, attachments: list[dict[str, Any]]) -> None:
        db.execute(
            "INSERT INTO messages(id,session_id,run_id,role,content,status,created_at) VALUES(?,?,?,?,?,?,?)",
            (message.id, message.session_id, message.run_id, message.role, message.content, message.status, message.created_at),
        )
        db.executemany(
            "INSERT INTO attachments(id,message_id,path,name,size,media_type) VALUES(?,?,?,?,?,?)",
            [(item["id"], message.id, item["path"], item["name"], item.get("size"), item.get("media_type") or item.get("mime_type")) for item in attachments],
        )
        db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (utc_now(), message.session_id))

    def update_message(self, message_id: str, *, content: str | None = None, status: str | None = None) -> None:
        fields: list[str] = []
        values: list[Any] = []
        if content is not None:
            fields.append("content=?")
            values.append(content)
        if status is not None:
            fields.append("status=?")
            values.append(status)
        if not fields:
            return
        values.append(message_id)
        with self.transaction() as db:
            db.execute(f"UPDATE messages SET {','.join(fields)} WHERE id=?", values)

    def add_run(self, run: Run) -> dict[str, Any]:
        with self.transaction() as db:
            db.execute(
                "INSERT INTO runs(id,session_id,objective,status,error,retry_of_run_id,retry_task_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (run.id, run.session_id, run.objective, str(run.status), run.error, run.retry_of_run_id, run.retry_task_id, run.created_at, run.updated_at),
            )
        return run.to_dict()

    def create_run_with_message(self, run: Run, message: Message, attachments: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            with self.transaction() as db:
                db.execute(
                    "INSERT INTO runs(id,session_id,objective,status,error,retry_of_run_id,retry_task_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (run.id, run.session_id, run.objective, str(run.status), run.error, run.retry_of_run_id, run.retry_task_id, run.created_at, run.updated_at),
                )
                self._insert_message(db, message, attachments)
        except sqlite3.IntegrityError as exc:
            raise ProtocolError("database_constraint", "run data violates a database constraint") from exc
        return {**run.to_dict(), "message": {**message.to_dict(), "attachments": attachments}}

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise ProtocolError("not_found", "run not found")
            result = dict(row)
            result["tasks"] = [dict(item) for item in db.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY position", (run_id,))]
        return result

    def update_run(self, run_id: str, status: RunStatus, error: str | None = None) -> None:
        with self.transaction() as db:
            db.execute("UPDATE runs SET status=?,error=?,updated_at=? WHERE id=?", (str(status), error, utc_now(), run_id))

    def add_tasks(self, tasks: list[AgentTask]) -> list[dict[str, Any]]:
        with self.transaction() as db:
            db.executemany(
                "INSERT INTO tasks(id,run_id,session_id,parent_id,description,effort,status,output,error,position,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        t.id,
                        t.run_id,
                        t.session_id,
                        t.parent_id,
                        t.description,
                        t.effort,
                        str(t.status),
                        t.output,
                        t.error,
                        t.position,
                        t.created_at,
                        t.updated_at,
                    )
                    for t in tasks
                ],
            )
        return [task.to_dict() for task in tasks]

    def update_task(self, task_id: str, status: TaskStatus, *, output: str | None = None, error: str | None = None) -> None:
        with self.transaction() as db:
            db.execute(
                "UPDATE tasks SET status=?,output=COALESCE(?,output),error=?,updated_at=? WHERE id=?",
                (str(status), output, error, utc_now(), task_id),
            )

    def get_run_attachments(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT a.* FROM attachments a JOIN messages m ON m.id=a.message_id WHERE m.run_id=? AND m.role='user' ORDER BY a.rowid",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_approval(self, value: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as db:
            db.execute(
                "INSERT INTO approvals(id,run_id,session_id,task_id,action,risk,status,approved,expires_at,created_at,resolved_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                tuple(
                    value.get(key)
                    for key in ("id", "run_id", "session_id", "task_id", "action", "risk", "status", "approved", "expires_at", "created_at", "resolved_at")
                ),
            )
        return value

    def resolve_approval(self, approval_id: str, status: str, approved: bool | None) -> None:
        with self.transaction() as db:
            changed = db.execute(
                "UPDATE approvals SET status=?,approved=?,resolved_at=? WHERE id=? AND status='pending'",
                (status, approved, utc_now(), approval_id),
            ).rowcount
            if not changed:
                raise ProtocolError("not_found", "approval request not found")

    def settings_get(self) -> dict[str, Any]:
        with self._connect() as db:
            values = {row["key"]: json.loads(row["value"]) for row in db.execute("SELECT key,value FROM settings")}
        return values

    def settings_update(self, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {"provider", "base_url", "model"}
        with self.transaction() as db:
            for key, value in values.items():
                if key in allowed:
                    db.execute(
                        "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, json.dumps(value)),
                    )
        return self.settings_get()

    def import_legacy(self, import_id: str, sessions: list[dict[str, Any]]) -> dict[str, Any]:
        return import_legacy(self, import_id, sessions)

    def database_info(self) -> dict[str, Any]:
        return database_info(self)

    def recover_interrupted(self) -> int:
        return recover_interrupted(self)
