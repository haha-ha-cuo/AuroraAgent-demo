import sqlite3

import pytest

from demo_agent.adapters.sqlite_repository import SqliteRepository
from demo_agent.domain.models import DEFAULT_PROJECT_ID, Message, Project, Session, utc_now
from demo_agent.protocol import ProtocolError


def test_sqlite_crud_and_wal(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "runtime.db")
    now = utc_now()
    session = Session("s1", "First", now, now)
    repository.create_session(session)
    repository.add_message(Message("m1", "s1", "user", "hello"), [{
        "id": "a1", "path": "C:/tmp/a.txt", "name": "a.txt", "size": 4, "mime_type": "text/plain"
    }])
    assert repository.get_session("s1")["messages"][0]["attachments"][0]["name"] == "a.txt"
    assert repository.rename_session("s1", "Renamed")["title"] == "Renamed"
    assert repository.database_info()["schema_version"] == 3
    assert repository.get_session("s1")["messages"][0]["attachments"][0]["media_type"] == "text/plain"
    with repository._connect() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    repository.delete_session("s1")
    assert repository.list_sessions() == []


def test_legacy_import_is_idempotent(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "runtime.db")
    payload = [{"id": "legacy-1", "title": "Old", "messages": [{"role": "user", "content": "hi"}]}]
    first = repository.import_legacy("import-1", payload)
    second = repository.import_legacy("import-1", payload)
    assert first == second == {"imported": 1, "skipped": 0, "failed": 0}
    assert repository.get_session("legacy-1")["messages"][0]["content"] == "hi"


def test_legacy_import_assigns_unique_message_ids(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "runtime.db")
    payload = [{"id": "legacy-1", "messages": [{"content": "one"}, {"content": "two"}]}]
    assert repository.import_legacy("multi", payload)["imported"] == 1
    assert [item["content"] for item in repository.get_session("legacy-1")["messages"]] == ["one", "two"]


def test_project_crud_and_session_membership(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "runtime.db")
    now = utc_now()
    project = repository.create_project(Project("p1", "Work", now, now))
    assert project["name"] == "Work"
    assert repository.list_projects()[0]["id"] == DEFAULT_PROJECT_ID
    session = Session("s1", "First", now, now, "p1")
    repository.create_session(session)
    assert repository.get_session("s1")["project_id"] == "p1"
    assert repository.rename_project("p1", "Renamed")["name"] == "Renamed"
    repository.delete_project("p1")
    with pytest.raises(ProtocolError):
        repository.get_project("p1")
    assert repository.list_sessions() == []


def test_settings_never_store_api_key(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "runtime.db")
    result = repository.settings_update({"provider": "openai", "model": "gpt", "api_key": "secret"})
    assert result["provider"] == "openai"
    with repository._connect() as db:
        assert db.execute("SELECT 1 FROM settings WHERE key='api_key'").fetchone() is None


def test_v2_migration_preserves_data_and_adds_constraints(tmp_path) -> None:
    path = tmp_path / "runtime.db"
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE sessions (id TEXT PRIMARY KEY,title TEXT NOT NULL,project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE messages (id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,run_id TEXT,role TEXT NOT NULL,content TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE runs (id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,objective TEXT NOT NULL,status TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE tasks (id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,parent_id TEXT,description TEXT NOT NULL,effort TEXT NOT NULL,status TEXT NOT NULL,output TEXT,error TEXT,position INTEGER NOT NULL);
        CREATE TABLE attachments (id TEXT PRIMARY KEY,message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,path TEXT NOT NULL,name TEXT NOT NULL,size INTEGER,mime_type TEXT);
        CREATE TABLE settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE legacy_imports (import_id TEXT PRIMARY KEY,imported_at TEXT NOT NULL,summary TEXT NOT NULL);
        INSERT INTO projects VALUES('project_default','默认项目','now','now');
        INSERT INTO sessions VALUES('s1','Old','project_default','now','now');
        INSERT INTO runs VALUES('r1','s1','work','completed',NULL,'now','now');
        INSERT INTO messages VALUES('m1','s1','r1','user','hello','completed','now');
        INSERT INTO tasks VALUES('t1','r1','s1',NULL,'work','low','completed','done',NULL,0);
        INSERT INTO attachments VALUES('a1','m1','/tmp/a.md','a.md',4,'text/markdown');
        PRAGMA user_version=2;
        """
    )
    db.close()
    repository = SqliteRepository(path)
    session = repository.get_session("s1")
    assert session["messages"][0]["attachments"][0]["media_type"] == "text/markdown"
    assert session["runs"][0]["tasks"][0]["created_at"] == "now"
    with repository._connect() as migrated:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 3
        assert migrated.execute("PRAGMA foreign_key_check").fetchall() == []
        assert {row["from"] for row in migrated.execute("PRAGMA foreign_key_list(messages)")} == {"session_id", "run_id"}


def test_v1_migration_assigns_default_project_and_preserves_session(tmp_path) -> None:
    path = tmp_path / "runtime.db"
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE messages (id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,run_id TEXT,role TEXT NOT NULL,content TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE runs (id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,objective TEXT NOT NULL,status TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE tasks (id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,parent_id TEXT,description TEXT NOT NULL,effort TEXT NOT NULL,status TEXT NOT NULL,output TEXT,error TEXT,position INTEGER NOT NULL);
        CREATE TABLE attachments (id TEXT PRIMARY KEY,message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,path TEXT NOT NULL,name TEXT NOT NULL,size INTEGER,mime_type TEXT);
        CREATE TABLE settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE legacy_imports (import_id TEXT PRIMARY KEY,imported_at TEXT NOT NULL,summary TEXT NOT NULL);
        INSERT INTO sessions VALUES('s1','Legacy','now','now');
        INSERT INTO messages VALUES('m1','s1',NULL,'user','kept','completed','now');
        PRAGMA user_version=1;
        """
    )
    db.close()
    repository = SqliteRepository(path)
    session = repository.get_session("s1")
    assert session["project_id"] == DEFAULT_PROJECT_ID
    assert session["messages"][0]["content"] == "kept"
    assert repository.database_info()["schema_version"] == 3
