import json
import os
import re
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from zhijing.backup import (
    DATABASE_NAME,
    FORMAT_NAME,
    FORMAT_VERSION,
    MANIFEST_NAME,
    create_backup,
    default_backup_path,
)
from zhijing.infra.db import SCHEMA_VERSION, Database
from zhijing.settings import StudySettings

ROOT = Path(__file__).resolve().parents[1]
THEME_ID = "0123456789ab"


def settings_at(tmp_path: Path) -> StudySettings:
    return StudySettings(
        _env_file=None,
        database=tmp_path / "state" / "study.db",
        theme_dir=tmp_path / "themes",
    )


def seed_data(settings: StudySettings) -> None:
    database = Database(settings.database)
    database.migrate()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO lessons (source, part, title, seconds, opened_at, markdown, revision)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("video/BV1abc123XYZ", 1, "合成课程", 12, 1, "## 合成笔记", 3),
        )
    theme = settings.theme_root / THEME_ID
    (theme / "nested").mkdir(parents=True)
    manifest = {"schemaVersion": 1, "name": "合成主题", "background": "background.png"}
    (theme / "theme.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (theme / "background.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"synthetic")
    (theme / "nested" / "rain.mp3").write_bytes(b"ID3synthetic")
    (settings.theme_root / ".staging-ignored").mkdir()
    (settings.theme_root / ".staging-ignored" / "theme.json").write_text("{}", encoding="utf-8")


def test_backup_archive_contains_manifest_database_and_themes(tmp_path: Path):
    settings = settings_at(tmp_path)
    seed_data(settings)
    target = create_backup(settings, tmp_path / "out" / "zhijing.zip")
    assert target == tmp_path / "out" / "zhijing.zip"
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        assert names[0] == MANIFEST_NAME
        assert DATABASE_NAME in names
        assert f"themes/{THEME_ID}/theme.json" in names
        assert f"themes/{THEME_ID}/background.png" in names
        assert f"themes/{THEME_ID}/nested/rain.mp3" in names
        assert not any(".staging" in name for name in names)
        assert not any(name.endswith(("-wal", "-shm")) for name in names)
        assert archive.testzip() is None
        manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
    assert manifest["format"] == FORMAT_NAME
    assert manifest["format_version"] == FORMAT_VERSION
    assert manifest["database"] == {"file": DATABASE_NAME, "schema_version": SCHEMA_VERSION}
    assert manifest["themes"] == {"count": 1, "ids": [THEME_ID]}
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest["created_at"])


def test_backup_database_snapshot_restores_rows(tmp_path: Path):
    settings = settings_at(tmp_path)
    seed_data(settings)
    target = create_backup(settings, tmp_path / "zhijing.zip")
    restored = tmp_path / "restored.sqlite3"
    with zipfile.ZipFile(target) as archive:
        restored.write_bytes(archive.read(DATABASE_NAME))
    with sqlite3.connect(restored) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        row = connection.execute("SELECT title, markdown, revision FROM lessons").fetchone()
    assert row == ("合成课程", "## 合成笔记", 3)


def test_backup_overwrites_atomically_without_leftovers(tmp_path: Path):
    settings = settings_at(tmp_path)
    seed_data(settings)
    output = tmp_path / "out" / "zhijing.zip"
    create_backup(settings, output)
    assert output.is_file()
    create_backup(settings, output)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
    assert [path.name for path in output.parent.iterdir()] == [output.name]


def test_failed_backup_leaves_no_partial_archive(tmp_path: Path):
    settings = settings_at(tmp_path)
    seed_data(settings)
    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(OSError):
        create_backup(settings, output)
    assert list(tmp_path.glob(".zhijing-backup-*")) == []
    assert [path.name for path in output.iterdir()] == []


def test_default_backup_path_uses_the_data_directory(tmp_path: Path):
    settings = settings_at(tmp_path)
    seed_data(settings)
    target = create_backup(settings)
    assert target.parent == settings.backup_root == tmp_path / "state" / "backups"
    assert re.fullmatch(r"zhijing-\d{8}-\d{6}\.zip", target.name)
    assert default_backup_path(settings).parent == settings.backup_root


def test_data_dir_controls_theme_and_backup_roots(tmp_path: Path, monkeypatch):
    for key in ("ZHIJING_STUDY_DATABASE", "ZHIJING_STUDY_DATA_DIR", "ZHIJING_STUDY_THEME_DIR"):
        monkeypatch.delenv(key, raising=False)
    defaults = StudySettings(_env_file=None)
    assert defaults.data_root == Path(".data")
    assert defaults.theme_root == Path(".data") / "themes"
    assert defaults.backup_root == Path(".data") / "backups"

    monkeypatch.setenv("ZHIJING_STUDY_DATA_DIR", str(tmp_path / "data"))
    configured = StudySettings(_env_file=None)
    assert configured.data_root == tmp_path / "data"
    assert configured.theme_root == tmp_path / "data" / "themes"
    assert configured.backup_root == tmp_path / "data" / "backups"

    monkeypatch.setenv("ZHIJING_STUDY_THEME_DIR", str(tmp_path / "custom-themes"))
    overridden = StudySettings(_env_file=None)
    assert overridden.theme_root == tmp_path / "custom-themes"
    assert overridden.backup_root == tmp_path / "data" / "backups"


def test_cli_writes_a_backup_with_the_output_option(tmp_path: Path):
    settings = settings_at(tmp_path)
    seed_data(settings)
    output = tmp_path / "cli" / "zhijing.zip"
    environment = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "ZHIJING_STUDY_DATABASE": str(settings.database),
        "ZHIJING_STUDY_THEME_DIR": str(settings.theme_root),
    }
    environment.pop("ZHIJING_STUDY_DATA_DIR", None)
    completed = subprocess.run(
        [sys.executable, str(ROOT / "dev" / "backup.py"), "--output", str(output)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    assert str(output) in completed.stdout
    with zipfile.ZipFile(output) as archive:
        assert MANIFEST_NAME in archive.namelist()
        assert DATABASE_NAME in archive.namelist()
