from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from demo_agent.adapters.sqlite_schema import MIGRATION_V1_TO_V2, SCHEMA_V2
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
    SCHEMA_VERSION = 2

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
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > self.SCHEMA_VERSION:
                raise RuntimeError(f"database version {version} is newer than supported")
            if version == 0:
                db.executescript(SCHEMA_V2)
                self._seed_default_project(db)
            elif version == 1:
                db.executescript(MIGRATION_V1_TO_V2)
                self._seed_default_project(db)
                db.execute("UPDATE sessions SET project_id=? WHERE project_id IS NULL", (DEFAULT_PROJECT_ID,))

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
        status = runs[-1]["status"] if runs else "idle"
        return {**dict(session), "status": status, "messages": messages, "runs": runs}

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
            db.execute(
                "INSERT INTO messages(id,session_id,run_id,role,content,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    message.id,
                    message.session_id,
                    message.run_id,
                    message.role,
                    message.content,
                    message.status,
                    message.created_at,
                ),
            )
            for attachment in attachments or []:
                db.execute(
                    "INSERT INTO attachments(id,message_id,path,name,size,mime_type) VALUES(?,?,?,?,?,?)",
                    (
                        attachment["id"],
                        message.id,
                        attachment["path"],
                        attachment["name"],
                        attachment.get("size"),
                        attachment.get("mime_type"),
                    ),
                )
            db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (utc_now(), message.session_id))
        value = message.to_dict()
        value["attachments"] = attachments or []
        return value

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
                "INSERT INTO runs(id,session_id,objective,status,error,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (run.id, run.session_id, run.objective, str(run.status), run.error, run.created_at, run.updated_at),
            )
        return run.to_dict()

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
                "INSERT INTO tasks(id,run_id,session_id,parent_id,description,effort,status,output,error,position) VALUES(?,?,?,?,?,?,?,?,?,?)",
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
                    )
                    for t in tasks
                ],
            )
        return [task.to_dict() for task in tasks]

    def update_task(self, task_id: str, status: TaskStatus, *, output: str | None = None, error: str | None = None) -> None:
        with self.transaction() as db:
            db.execute(
                "UPDATE tasks SET status=?,output=COALESCE(?,output),error=? WHERE id=?",
                (str(status), output, error, task_id),
            )

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

    def import_legacy(self, import_id: str, sessions: list[dict[str, Any]]) -> dict[str, int]:
        imported = skipped = failed = 0
        with self.transaction() as db:
            existing = db.execute("SELECT summary FROM legacy_imports WHERE import_id=?", (import_id,)).fetchone()
            if existing:
                return json.loads(existing["summary"])
            for index, raw in enumerate(sessions):
                savepoint = f"legacy_{index}"
                db.execute(f"SAVEPOINT {savepoint}")
                try:
                    session_id = str(raw["id"])
                    title = str(raw.get("title") or "导入的会话")[:200]
                    created = str(raw.get("createdAt") or raw.get("created_at") or utc_now())
                    if db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone():
                        skipped += 1
                        continue
                    db.execute(
                        "INSERT INTO sessions(id,title,project_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (session_id, title, DEFAULT_PROJECT_ID, created, created),
                    )
                    for raw_message in raw.get("messages", []):
                        db.execute(
                            "INSERT INTO messages(id,session_id,run_id,role,content,status,created_at) VALUES(?,?,?,?,?,?,?)",
                            (
                                str(raw_message.get("id") or f"legacy_{session_id}_{imported}"),
                                session_id,
                                None,
                                str(raw_message.get("role") or "assistant"),
                                str(raw_message.get("content") or ""),
                                "completed",
                                str(raw_message.get("createdAt") or created),
                            ),
                        )
                    imported += 1
                    db.execute(f"RELEASE SAVEPOINT {savepoint}")
                except (KeyError, TypeError, ValueError, sqlite3.IntegrityError):
                    db.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    db.execute(f"RELEASE SAVEPOINT {savepoint}")
                    failed += 1
            summary = {"imported": imported, "skipped": skipped, "failed": failed}
            db.execute("INSERT INTO legacy_imports VALUES(?,?,?)", (import_id, utc_now(), json.dumps(summary)))
        return summary

    def database_info(self) -> dict[str, Any]:
        with self._connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        return {"path": str(self.path), "schema_version": version, "session_count": sessions}

    def recover_interrupted(self) -> int:
        with self.transaction() as db:
            rows = db.execute("SELECT id FROM runs WHERE status IN ('queued','running','waiting')").fetchall()
            run_ids = [row["id"] for row in rows]
            if run_ids:
                placeholders = ",".join("?" for _ in run_ids)
                db.execute(
                    f"UPDATE tasks SET status='failed',error='runtime interrupted' WHERE run_id IN ({placeholders}) AND status IN ('queued','running','waiting')",
                    run_ids,
                )
                db.execute(
                    f"UPDATE runs SET status='failed',error='runtime interrupted',updated_at=? WHERE id IN ({placeholders})",
                    [utc_now(), *run_ids],
                )
        return len(run_ids)
