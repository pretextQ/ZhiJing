"""SQLite connections, schema migrations and consistent snapshots."""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5000

# Migrations keyed by the PRAGMA user_version they upgrade to. v1 matches the lessons
# table that existed before migrations, so old databases upgrade in place without losing rows.
MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        """
        CREATE TABLE IF NOT EXISTS lessons (
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
        """,
        "CREATE INDEX IF NOT EXISTS idx_lessons_opened_at ON lessons (opened_at DESC, id DESC)",
    ),
}


class Database:
    """A SQLite file with migrations applied once at application startup."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Open one configured connection; commit on success, roll back on error, then close."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA journal_mode = WAL")
            with connection:
                yield connection
        finally:
            connection.close()

    def schema_version(self) -> int:
        with self.connect() as connection:
            return _user_version(connection)

    def migrate(self) -> int:
        """Apply pending migrations once; safe to call on every development or app startup."""
        with self.connect() as connection:
            version = _user_version(connection)
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"数据库版本 {version} 高于程序支持的 {SCHEMA_VERSION}")
            if version == SCHEMA_VERSION:
                return version
            connection.execute("BEGIN IMMEDIATE")
            for target in range(version + 1, SCHEMA_VERSION + 1):
                for statement in MIGRATIONS[target]:
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {target}")
            return SCHEMA_VERSION

    def snapshot(self, destination: Path | str) -> Path:
        """Write a consistent, single-file copy of the database, including committed WAL content."""
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source:
            with closing(sqlite3.connect(target)) as copy:
                source.backup(copy)
        with closing(sqlite3.connect(target)) as copy:
            copy.execute("PRAGMA journal_mode = DELETE")
        return target


def _user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0])
