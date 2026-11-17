import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from zhijing.backup import MANIFEST_NAME, create_backup
from zhijing.infra.db import Database
from zhijing.restore import RestoreError, inspect_backup, restore_backup
from zhijing.settings import StudySettings

ROOT = Path(__file__).resolve().parents[1]
THEME_ID = "0123456789ab"


def settings_at(tmp_path: Path) -> StudySettings:
    return StudySettings(
        _env_file=None,
        database=tmp_path / "state" / "study.db",
        theme_dir=tmp_path / "themes",
    )


def seed(settings: StudySettings, title: str = "合成课程", theme: str | None = THEME_ID) -> None:
    database = Database(settings.database)
    database.migrate()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO lessons (source, part, title, seconds, opened_at, markdown, revision)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("video/BV1abc123XYZ", 1, title, 12, 1, "## 合成笔记", 3),
        )
    if theme:
        directory = settings.theme_root / theme
        (directory / "nested").mkdir(parents=True)
        (directory / "theme.json").write_text(
            json.dumps({"schemaVersion": 1, "name": "合成主题", "background": "background.png"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (directory / "background.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"synthetic")
        (directory / "nested" / "rain.mp3").write_bytes(b"ID3synthetic")


def make_backup(tmp_path: Path, *, title: str = "合成课程", theme: str | None = THEME_ID) -> tuple[StudySettings, Path]:
    source = settings_at(tmp_path / "source")
    seed(source, title, theme)
    archive = create_backup(source, tmp_path / "zhijing.zip")
    return source, archive


def test_inspect_reports_manifest_without_writing(tmp_path: Path):
    _, archive = make_backup(tmp_path)
    info = inspect_backup(archive)
    assert info.schema_version >= 1
    assert info.theme_ids == [THEME_ID]
    assert info.has_lessons is True
    assert info.database_bytes > 0
    assert info.created_at.endswith("Z")


def test_restore_replaces_database_and_themes(tmp_path: Path):
    _, archive = make_backup(tmp_path)
    target = settings_at(tmp_path / "target")
    result = restore_backup(target, archive)
    assert result.database == target.database
    assert result.themes == 1
    with sqlite3.connect(target.database) as connection:
        assert connection.execute("SELECT title, markdown, revision FROM lessons").fetchone() == (
            "合成课程",
            "## 合成笔记",
            3,
        )
    assert (target.theme_root / THEME_ID / "nested" / "rain.mp3").read_bytes() == b"ID3synthetic"


def test_restore_into_existing_data_keeps_previous_copy(tmp_path: Path):
    _, archive = make_backup(tmp_path, title="旧笔记")
    target = settings_at(tmp_path / "target")
    seed(target, title="当前笔记")
    result = restore_backup(target, archive, force=True)
    assert len(result.preserved) == 2
    assert all(path.exists() for path in result.preserved)
    archived = [path for path in result.preserved if ".pre-restore-" in path.name]
    assert archived
    with sqlite3.connect(target.database) as connection:
        assert connection.execute("SELECT title FROM lessons").fetchone() == ("旧笔记",)


def test_restore_refuses_to_overwrite_live_notes_without_force(tmp_path: Path):
    _, archive = make_backup(tmp_path)
    target = settings_at(tmp_path / "target")
    seed(target, title="当前笔记")
    with pytest.raises(RestoreError, match="--force"):
        restore_backup(target, archive)
    with sqlite3.connect(target.database) as connection:
        assert connection.execute("SELECT title FROM lessons").fetchone() == ("当前笔记",)


def test_restore_removes_stale_wal_sidecars(tmp_path: Path):
    _, archive = make_backup(tmp_path)
    target = settings_at(tmp_path / "target")
    target.database.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(f"{target.database}{suffix}").write_bytes(b"stale")
    restore_backup(target, archive, force=True)
    for suffix in ("-wal", "-shm"):
        assert not Path(f"{target.database}{suffix}").exists()


def test_restore_accepts_a_backup_without_themes(tmp_path: Path):
    _, archive = make_backup(tmp_path, theme=None)
    target = settings_at(tmp_path / "target")
    seed(target, theme="fedcba987654")
    result = restore_backup(target, archive, force=True)
    assert result.themes == 0
    assert not target.theme_root.exists()


def test_restore_rejects_archives_that_escape_the_root(tmp_path: Path):
    settings = settings_at(tmp_path / "source")
    seed(settings)
    archive = create_backup(settings, tmp_path / "zhijing.zip")
    tampered = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info))
        target.writestr("themes/../../evil.txt", b"boom")
    with pytest.raises(RestoreError, match="路径不安全|主题目录名不合法"):
        inspect_backup(tampered)


def test_restore_rejects_unknown_archives(tmp_path: Path):
    plain = tmp_path / "plain.zip"
    with zipfile.ZipFile(plain, "w") as archive:
        archive.writestr("readme.txt", "not a backup")
    with pytest.raises(RestoreError):
        inspect_backup(plain)
    missing = tmp_path / "missing.zip"
    with pytest.raises(RestoreError, match="找不到备份文件"):
        inspect_backup(missing)


def test_restore_rejects_a_newer_schema(tmp_path: Path):
    _, archive = make_backup(tmp_path)
    newer = tmp_path / "newer.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(newer, "w") as target:
        manifest = json.loads(source.read(MANIFEST_NAME))
        manifest["database"]["schema_version"] = 999
        target.writestr(MANIFEST_NAME, json.dumps(manifest))
        for info in source.infolist():
            if info.filename != MANIFEST_NAME:
                target.writestr(info, source.read(info))
    with pytest.raises(RestoreError, match="更新的版本"):
        inspect_backup(newer)


def test_restore_leaves_no_staging_directories(tmp_path: Path):
    _, archive = make_backup(tmp_path)
    target = settings_at(tmp_path / "target")
    restore_backup(target, archive, force=True)
    leftovers = [path.name for path in target.data_root.iterdir() if path.name.startswith(".restore-")]
    assert leftovers == []


def test_restore_cli_inspect_and_apply(tmp_path: Path):
    _, archive = make_backup(tmp_path)
    target = settings_at(tmp_path / "target")
    environment = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "ZHIJING_STUDY_DATABASE": str(target.database),
        "ZHIJING_STUDY_THEME_DIR": str(target.theme_root),
    }
    environment.pop("ZHIJING_STUDY_DATA_DIR", None)
    inspected = subprocess.run(
        [sys.executable, str(ROOT / "dev" / "restore.py"), str(archive), "--inspect"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert inspected.returncode == 0, inspected.stderr
    assert THEME_ID in inspected.stdout
    applied = subprocess.run(
        [sys.executable, str(ROOT / "dev" / "restore.py"), str(archive), "--force"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert applied.returncode == 0, applied.stderr
    assert target.database.is_file()
