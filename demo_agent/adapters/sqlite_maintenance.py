from __future__ import annotations

import json
import sqlite3
from typing import Any

from demo_agent.domain.models import DEFAULT_PROJECT_ID, utc_now


def import_legacy(repository: Any, import_id: str, sessions: list[dict[str, Any]]) -> dict[str, Any]:
    imported = skipped = failed = 0
    failures: list[dict[str, Any]] = []
    with repository.transaction() as db:
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
                else:
                    db.execute(
                        "INSERT INTO sessions(id,title,project_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (session_id, title, DEFAULT_PROJECT_ID, created, created),
                    )
                    for message_index, raw_message in enumerate(raw.get("messages", [])):
                        message_id = str(raw_message.get("id") or f"legacy_{session_id}_{message_index}")
                        db.execute(
                            "INSERT INTO messages(id,session_id,run_id,role,content,status,created_at) VALUES(?,?,?,?,?,?,?)",
                            (
                                message_id,
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
            except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as exc:
                db.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                db.execute(f"RELEASE SAVEPOINT {savepoint}")
                failed += 1
                failures.append({"index": index, "reason": type(exc).__name__})
        summary: dict[str, Any] = {"imported": imported, "skipped": skipped, "failed": failed}
        if failures:
            summary["failures"] = failures
        db.execute("INSERT INTO legacy_imports VALUES(?,?,?)", (import_id, utc_now(), json.dumps(summary)))
    return summary


def database_info(repository: Any) -> dict[str, Any]:
    with repository._connect() as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    return {"path": str(repository.path), "schema_version": version, "session_count": sessions}


def recover_interrupted(repository: Any) -> int:
    now = utc_now()
    with repository.transaction() as db:
        rows = db.execute("SELECT id FROM runs WHERE status IN ('queued','running','waiting')").fetchall()
        run_ids = [row["id"] for row in rows]
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            db.execute(
                f"UPDATE tasks SET status='failed',error='runtime interrupted',updated_at=? WHERE run_id IN ({placeholders}) AND status IN ('queued','running','waiting')",
                [now, *run_ids],
            )
            db.execute(
                f"UPDATE approvals SET status='expired',resolved_at=? WHERE run_id IN ({placeholders}) AND status='pending'",
                [now, *run_ids],
            )
            db.execute(
                f"UPDATE runs SET status='failed',error='runtime interrupted',updated_at=? WHERE id IN ({placeholders})",
                [now, *run_ids],
            )
    return len(run_ids)
