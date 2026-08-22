SCHEMA_V2 = """
CREATE TABLE projects (
    id TEXT PRIMARY KEY, name TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE sessions (
    id TEXT PRIMARY KEY, title TEXT NOT NULL,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE messages (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    run_id TEXT, role TEXT NOT NULL, content TEXT NOT NULL,
    status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE runs (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    objective TEXT NOT NULL, status TEXT NOT NULL, error TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE tasks (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    parent_id TEXT, description TEXT NOT NULL, effort TEXT NOT NULL,
    status TEXT NOT NULL, output TEXT, error TEXT, position INTEGER NOT NULL
);
CREATE TABLE attachments (
    id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    path TEXT NOT NULL, name TEXT NOT NULL, size INTEGER, mime_type TEXT
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE legacy_imports (import_id TEXT PRIMARY KEY, imported_at TEXT NOT NULL, summary TEXT NOT NULL);
CREATE INDEX idx_messages_session ON messages(session_id, created_at);
CREATE INDEX idx_runs_session ON runs(session_id, created_at);
CREATE INDEX idx_tasks_run ON tasks(run_id, position);
PRAGMA user_version = 2;
"""

MIGRATION_V1_TO_V2 = """
CREATE TABLE projects (
    id TEXT PRIMARY KEY, name TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
ALTER TABLE sessions ADD COLUMN project_id TEXT REFERENCES projects(id) ON DELETE CASCADE;
PRAGMA user_version = 2;
"""
