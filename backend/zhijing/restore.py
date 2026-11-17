"""Restore a Zhijing backup archive into the configured data directory.

The counterpart to :mod:`zhijing.backup`. A restore validates the manifest, the archive
paths and the SQLite snapshot before touching live data, stages everything in a temporary
directory next to the data root, and only then swaps the database and the theme folder in.
Existing data is moved aside with a `.pre-restore` suffix instead of being deleted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp

from .backup import DATABASE_NAME, FORMAT_NAME, FORMAT_VERSION, MANIFEST_NAME, THEMES_PREFIX
from .infra.db import SCHEMA_VERSION, Database
from .settings import StudySettings

RESTORE_SUFFIX = ".pre-restore"
STAGING_PREFIX = ".restore-"
THEME_ID = re.compile(r"[0-9a-f]{12}")


class RestoreError(RuntimeError):
    """Raised when an archive cannot be restored safely."""


@dataclass(frozen=True)
class BackupInfo:
    archive: Path
    created_at: str
    schema_version: int
    theme_ids: list[str]
    database_bytes: int
    has_lessons: bool


@dataclass(frozen=True)
class RestoreResult:
    database: Path
    themes: int
    preserved: list[Path]


def inspect_backup(archive: Path) -> BackupInfo:
    """Validate an archive and return its manifest summary without writing anything."""
    archive = Path(archive)
    if not archive.is_file():
        raise RestoreError(f"找不到备份文件：{archive}")
    try:
        with zipfile.ZipFile(archive) as bundle:
            names = set(bundle.namelist())
            if MANIFEST_NAME not in names:
                raise RestoreError("备份里缺少 manifest.json，可能不是知径备份")
            if DATABASE_NAME not in names:
                raise RestoreError("备份里缺少 study.sqlite3")
            manifest = _read_manifest(bundle)
            for info in bundle.infolist():
                _check_entry(info)
            snapshot = _read_database(bundle)
    except zipfile.BadZipFile as error:
        raise RestoreError("备份文件不是有效的 ZIP") from error
    theme_ids = _theme_ids(manifest, names)
    schema_version = int(manifest.get("database", {}).get("schema_version", 0))
    if schema_version > SCHEMA_VERSION:
        raise RestoreError(
            f"备份来自更新的版本（schema {schema_version}，当前支持 {SCHEMA_VERSION}），请先升级知径"
        )
    return BackupInfo(
        archive=archive,
        created_at=str(manifest.get("created_at", "")),
        schema_version=schema_version,
        theme_ids=theme_ids,
        database_bytes=len(snapshot),
        has_lessons=_count_lessons(snapshot) > 0,
    )


def restore_backup(settings: StudySettings, archive: Path, *, force: bool = False) -> RestoreResult:
    """Replace the live database and theme folder with the contents of *archive*.

    Refuses to overwrite a database that still holds lessons unless *force* is set. The
    previous database and theme folder are kept next to the new ones with a
    `RESTORE_SUFFIX` suffix so a restore can always be undone by hand.
    """
    info = inspect_backup(archive)
    data_root = settings.data_root
    if not force and settings.database.is_file() and _live_lessons(settings.database) > 0:
        raise RestoreError("当前数据目录已有笔记；确认覆盖请加 --force（原有数据会保留为 .pre-restore）")

    data_root.mkdir(parents=True, exist_ok=True)
    staging = Path(mkdtemp(dir=data_root, prefix=STAGING_PREFIX))
    preserved: list[Path] = []
    try:
        staged_database, staged_themes = _stage(archive, staging)
        _verify_database(staged_database)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        preserved = _move_aside(settings, stamp)
        settings.database.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_database, settings.database)
        for suffix in ("-wal", "-shm"):
            Path(f"{settings.database}{suffix}").unlink(missing_ok=True)
        theme_root = settings.theme_root
        if staged_themes is not None:
            theme_root.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_themes, theme_root)
        elif theme_root.exists():
            shutil.rmtree(theme_root)
        Database(settings.database).migrate()
        return RestoreResult(database=settings.database, themes=len(info.theme_ids), preserved=preserved)
    except BaseException:
        _rollback(settings, preserved)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _read_manifest(bundle: zipfile.ZipFile) -> dict:
    try:
        manifest = json.loads(bundle.read(MANIFEST_NAME).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RestoreError("备份里的 manifest.json 无法解析") from error
    if not isinstance(manifest, dict):
        raise RestoreError("备份里的 manifest.json 格式不正确")
    if manifest.get("format") != FORMAT_NAME:
        raise RestoreError("这不是知径的备份文件")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise RestoreError(f"不支持的备份格式版本：{manifest.get('format_version')}")
    database = manifest.get("database")
    if not isinstance(database, dict) or database.get("file") != DATABASE_NAME:
        raise RestoreError("manifest.json 里的数据库信息不正确")
    if not isinstance(database.get("schema_version"), int):
        raise RestoreError("manifest.json 缺少数据库版本")
    return manifest


def _check_entry(info: zipfile.ZipInfo) -> None:
    """Reject symlinks, directories entries with odd names, and anything escaping the archive root."""
    name = info.filename
    if name.endswith("/"):
        return
    if name in {MANIFEST_NAME, DATABASE_NAME}:
        return
    if not name.startswith(f"{THEMES_PREFIX}/"):
        raise RestoreError(f"备份里出现了意外的条目：{name}")
    if (info.external_attr >> 16) & 0o170000 == 0o120000:
        raise RestoreError(f"备份里含有符号链接，拒绝恢复：{name}")
    relative = name[len(THEMES_PREFIX) + 1 :]
    parts = relative.split("/")
    if len(parts) < 2 or not THEME_ID.fullmatch(parts[0]):
        raise RestoreError(f"备份里的主题目录名不合法：{name}")
    for part in parts:
        if part in {"", ".", ".."} or "\\" in part or any(ord(char) < 32 for char in part):
            raise RestoreError(f"备份里的路径不安全：{name}")


def _theme_ids(manifest: dict, names: set[str]) -> list[str]:
    recorded = manifest.get("themes", {}).get("ids", [])
    found: list[str] = []
    for name in names:
        if name.startswith(f"{THEMES_PREFIX}/"):
            theme_id = name[len(THEMES_PREFIX) + 1 :].split("/", 1)[0]
            if theme_id and theme_id not in found:
                found.append(theme_id)
    for theme_id in recorded:
        if theme_id not in found:
            raise RestoreError(f"manifest.json 记录了主题 {theme_id}，但备份里没有对应文件")
    return sorted(found)


def _read_database(bundle: zipfile.ZipFile) -> bytes:
    try:
        return bundle.read(DATABASE_NAME)
    except KeyError as error:
        raise RestoreError("备份里缺少 study.sqlite3") from error


def _stage(archive: Path, staging: Path) -> tuple[Path, Path | None]:
    staged_database = staging / DATABASE_NAME
    theme_root = staging / THEMES_PREFIX
    has_themes = False
    with zipfile.ZipFile(archive) as bundle:
        staged_database.write_bytes(bundle.read(DATABASE_NAME))
        for info in bundle.infolist():
            if info.filename.endswith("/") or info.filename in {MANIFEST_NAME, DATABASE_NAME}:
                continue
            relative = info.filename[len(THEMES_PREFIX) + 1 :]
            target = theme_root / Path(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(info))
            has_themes = True
    return staged_database, theme_root if has_themes else None


def _verify_database(path: Path) -> None:
    try:
        # closing() matters on Windows: an open handle would block the later os.replace.
        with closing(sqlite3.connect(path)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RestoreError("备份里的数据库完整性校验失败")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    except sqlite3.DatabaseError as error:
        raise RestoreError("备份里的数据库无法读取") from error
    if version > SCHEMA_VERSION:
        raise RestoreError(f"备份数据库版本 {version} 高于当前支持的 {SCHEMA_VERSION}")


def _count_lessons(snapshot: bytes) -> int:
    staging = Path(mkdtemp(prefix=".restore-inspect-"))
    try:
        path = staging / DATABASE_NAME
        path.write_bytes(snapshot)
        return _live_lessons(path)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _live_lessons(path: Path) -> int:
    try:
        with closing(sqlite3.connect(path)) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM lessons").fetchone()[0])
    except sqlite3.DatabaseError:
        return 0


def _move_aside(settings: StudySettings, stamp: str) -> list[Path]:
    preserved: list[Path] = []
    if settings.database.is_file():
        target = settings.database.with_name(f"{settings.database.name}{RESTORE_SUFFIX}-{stamp}")
        os.replace(settings.database, target)
        preserved.append(target)
    theme_root = settings.theme_root
    if theme_root.exists():
        target = theme_root.with_name(f"{theme_root.name}{RESTORE_SUFFIX}-{stamp}")
        os.replace(theme_root, target)
        preserved.append(target)
    return preserved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从备份恢复知径数据库与主题")
    parser.add_argument("archive", type=Path, help="备份 ZIP 路径")
    parser.add_argument("--inspect", action="store_true", help="只查看备份内容，不写入任何文件")
    parser.add_argument("--force", action="store_true", help="当前已有笔记时仍然覆盖（原数据保留为 .pre-restore）")
    args = parser.parse_args(argv)
    try:
        info = inspect_backup(args.archive)
        print(f"备份：{info.archive}")
        print(f"创建时间：{info.created_at or '未知'}")
        print(
            f"数据库版本：schema {info.schema_version}，{info.database_bytes} 字节，"
            f"{'含笔记' if info.has_lessons else '无笔记'}"
        )
        print(f"主题：{len(info.theme_ids)} 个" + (f"（{', '.join(info.theme_ids)}）" if info.theme_ids else ""))
        if args.inspect:
            return 0
        result = restore_backup(StudySettings(), args.archive, force=args.force)
    except RestoreError as error:
        print(f"恢复失败：{error}", file=sys.stderr)
        return 1
    print(f"已恢复数据库：{result.database}")
    print(f"已恢复主题：{result.themes} 个")
    for kept in result.preserved:
        print(f"原有数据已保留：{kept}")
    return 0


def _rollback(settings: StudySettings, preserved: list[Path]) -> None:
    """Put the previous database and theme folder back if the swap failed halfway."""
    for target in preserved:
        name = target.name
        if f"{settings.database.name}{RESTORE_SUFFIX}-" in name:
            os.replace(target, settings.database)
        elif f"{settings.theme_root.name}{RESTORE_SUFFIX}-" in name:
            os.replace(target, settings.theme_root)


if __name__ == "__main__":
    raise SystemExit(main())
