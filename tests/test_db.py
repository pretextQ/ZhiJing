import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhijing.infra.db import BUSY_TIMEOUT_MS, SCHEMA_VERSION, Database
from zhijing.main import create_app
from zhijing.settings import Settings, StudySettings

LEGACY_SCHEMA = """
CREATE TABLE lessons (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    part INTEGER NOT NULL,
    title TEXT NOT NULL,
    seconds INTEGER NOT NULL DEFAULT 0,
    opened_at INTEGER NOT NULL,
    markdown TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 0,
    export_path TEXT,
    export_digest TEXT,
    UNIQUE (source, part)
)
"""


def user_version(path: Path) -> int:
    with sqlite3.connect(path) as connection:
        return connection.execute("PRAGMA user_version").fetchone()[0]


def insert_lesson(database: Database, title: str = "合成课程", markdown: str = "## 合成笔记") -> None:
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO lessons (source, part, title, seconds, opened_at, markdown, revision)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("video/BV1abc123XYZ", 1, title, 12, 1, markdown, 3),
        )


def test_empty_database_is_migrated_and_connections_are_configured(tmp_path: Path):
    database = Database(tmp_path / "state" / "study.db")
    assert database.migrate() == SCHEMA_VERSION
    assert database.schema_version() == SCHEMA_VERSION
    with database.connect() as connection:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        indexes = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
        assert "lessons" in tables
        assert "idx_lessons_opened_at" in indexes
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == BUSY_TIMEOUT_MS


def test_migrate_is_idempotent_and_keeps_rows(tmp_path: Path):
    database = Database(tmp_path / "study.db")
    database.migrate()
    insert_lesson(database)
    assert database.migrate() == SCHEMA_VERSION
    assert database.migrate() == SCHEMA_VERSION
    with database.connect() as connection:
        row = connection.execute("SELECT title, markdown, revision FROM lessons").fetchone()
        assert row["title"] == "合成课程"
        assert row["markdown"] == "## 合成笔记"
        assert row["revision"] == 3


def test_legacy_database_without_user_version_upgrades_in_place(tmp_path: Path):
    path = tmp_path / "legacy" / "study.db"
    path.parent.mkdir()
    with sqlite3.connect(path) as connection:
        connection.execute(LEGACY_SCHEMA)
        connection.execute(
            "INSERT INTO lessons (source, part, title, seconds, opened_at, markdown, revision)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("video/BV1abc123XYZ", 1, "旧课程", 12, 1, "旧笔记", 3),
        )
    assert user_version(path) == 0
    database = Database(path)
    assert database.migrate() == SCHEMA_VERSION
    with database.connect() as connection:
        row = connection.execute("SELECT title, markdown, revision FROM lessons").fetchone()
        indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
        assert row["title"] == "旧课程"
        assert row["markdown"] == "旧笔记"
        assert row["revision"] == 3
        assert "idx_lessons_opened_at" in indexes
    assert user_version(path) == SCHEMA_VERSION


def test_migrate_rejects_a_newer_schema_version(tmp_path: Path):
    path = tmp_path / "study.db"
    Database(path).migrate()
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(RuntimeError):
        Database(path).migrate()


def test_snapshot_is_a_consistent_single_file_copy(tmp_path: Path):
    database = Database(tmp_path / "state" / "study.db")
    database.migrate()
    insert_lesson(database)
    target = database.snapshot(tmp_path / "out" / "snapshot.sqlite3")
    assert target.is_file()
    assert not target.with_name(target.name + "-wal").exists()
    assert not target.with_name(target.name + "-shm").exists()
    with sqlite3.connect(target) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT title FROM lessons").fetchone()[0] == "合成课程"


def test_application_startup_migrates_before_requests(tmp_path: Path):
    path = tmp_path / "state" / "study.db"
    app = create_app(Settings(_env_file=None), StudySettings(_env_file=None, database=path))
    with TestClient(app, base_url="http://127.0.0.1:18081") as api:
        assert api.get("/api/study").status_code == 200
        assert user_version(path) == SCHEMA_VERSION
        with sqlite3.connect(path) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            assert "lessons" in tables
