SCHEMA_V3 = """
CREATE TABLE projects (
    id TEXT PRIMARY KEY, name TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE sessions (
    id TEXT PRIMARY KEY, title TEXT NOT NULL,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE runs (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    objective TEXT NOT NULL, status TEXT NOT NULL, error TEXT,
    retry_of_run_id TEXT REFERENCES runs(id) ON DELETE SET NULL, retry_task_id TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE messages (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL, role TEXT NOT NULL,
    content TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE tasks (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
    description TEXT NOT NULL, effort TEXT NOT NULL, status TEXT NOT NULL,
    output TEXT, error TEXT, position INTEGER NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(run_id, position)
);
CREATE TABLE attachments (
    id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    path TEXT NOT NULL, name TEXT NOT NULL, size INTEGER, media_type TEXT
);
CREATE TABLE approvals (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
    action TEXT NOT NULL, risk TEXT NOT NULL, status TEXT NOT NULL,
    approved INTEGER, expires_at TEXT NOT NULL, created_at TEXT NOT NULL, resolved_at TEXT
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE legacy_imports (import_id TEXT PRIMARY KEY, imported_at TEXT NOT NULL, summary TEXT NOT NULL);
CREATE INDEX idx_messages_session ON messages(session_id, created_at);
CREATE INDEX idx_runs_session ON runs(session_id, created_at);
CREATE INDEX idx_tasks_run ON tasks(run_id, position);
CREATE INDEX idx_approvals_session ON approvals(session_id, created_at);
PRAGMA user_version = 3;
"""

MIGRATION_V1_TO_V2 = """
CREATE TABLE projects (
    id TEXT PRIMARY KEY, name TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
ALTER TABLE sessions ADD COLUMN project_id TEXT REFERENCES projects(id) ON DELETE CASCADE;
INSERT INTO projects(id,name,created_at,updated_at)
VALUES('project_default','默认项目',strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now'));
UPDATE sessions SET project_id='project_default' WHERE project_id IS NULL;
PRAGMA user_version = 2;
"""

MIGRATION_V2_TO_V3 = """
INSERT OR IGNORE INTO projects(id,name,created_at,updated_at)
VALUES('project_default','默认项目',strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now'));
UPDATE sessions SET project_id='project_default' WHERE project_id IS NULL;
CREATE TABLE runs_v3 (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    objective TEXT NOT NULL, status TEXT NOT NULL, error TEXT,
    retry_of_run_id TEXT REFERENCES runs_v3(id) ON DELETE SET NULL, retry_task_id TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
INSERT INTO runs_v3(id,session_id,objective,status,error,created_at,updated_at)
SELECT id,session_id,objective,status,error,created_at,updated_at FROM runs;
CREATE TABLE messages_v3 (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs_v3(id) ON DELETE SET NULL, role TEXT NOT NULL,
    content TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
INSERT INTO messages_v3(id,session_id,run_id,role,content,status,created_at)
SELECT m.id,m.session_id,CASE WHEN r.id IS NULL THEN NULL ELSE m.run_id END,m.role,m.content,m.status,m.created_at
FROM messages m LEFT JOIN runs r ON r.id=m.run_id;
CREATE TABLE tasks_v3 (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs_v3(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES tasks_v3(id) ON DELETE CASCADE,
    description TEXT NOT NULL, effort TEXT NOT NULL, status TEXT NOT NULL,
    output TEXT, error TEXT, position INTEGER NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(run_id, position)
);
INSERT INTO tasks_v3(id,run_id,session_id,parent_id,description,effort,status,output,error,position,created_at,updated_at)
SELECT t.id,t.run_id,t.session_id,CASE WHEN p.id IS NULL THEN NULL ELSE t.parent_id END,
       t.description,t.effort,t.status,t.output,t.error,t.position,r.created_at,r.updated_at
FROM tasks t JOIN runs r ON r.id=t.run_id LEFT JOIN tasks p ON p.id=t.parent_id;
CREATE TABLE attachments_v3 (
    id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages_v3(id) ON DELETE CASCADE,
    path TEXT NOT NULL, name TEXT NOT NULL, size INTEGER, media_type TEXT
);
INSERT INTO attachments_v3(id,message_id,path,name,size,media_type)
SELECT id,message_id,path,name,size,mime_type FROM attachments;
DROP TABLE attachments;
DROP TABLE tasks;
DROP TABLE messages;
DROP TABLE runs;
ALTER TABLE runs_v3 RENAME TO runs;
ALTER TABLE messages_v3 RENAME TO messages;
ALTER TABLE tasks_v3 RENAME TO tasks;
ALTER TABLE attachments_v3 RENAME TO attachments;
CREATE TABLE approvals (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
    action TEXT NOT NULL, risk TEXT NOT NULL, status TEXT NOT NULL,
    approved INTEGER, expires_at TEXT NOT NULL, created_at TEXT NOT NULL, resolved_at TEXT
);
CREATE INDEX idx_messages_session ON messages(session_id, created_at);
CREATE INDEX idx_runs_session ON runs(session_id, created_at);
CREATE INDEX idx_tasks_run ON tasks(run_id, position);
CREATE INDEX idx_approvals_session ON approvals(session_id, created_at);
PRAGMA user_version = 3;
"""
