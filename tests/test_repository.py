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
    assert repository.database_info()["schema_version"] == 2
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
