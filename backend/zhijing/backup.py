"""ZIP backups of the Zhijing data directory: a consistent database snapshot plus themes."""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkstemp

from .infra.db import Database
from .settings import StudySettings

FORMAT_NAME = "zhijing-backup"
FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATABASE_NAME = "study.sqlite3"
THEMES_PREFIX = "themes"
TEMP_PREFIX = ".zhijing-backup-"


def default_backup_path(settings: StudySettings) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return settings.backup_root / f"zhijing-{stamp}.zip"


def create_backup(settings: StudySettings, output: Path | str | None = None) -> Path:
    """Write a portable backup archive atomically and return its path.

    The archive contains manifest.json, a SQLite snapshot in WAL-safe form, and every
    imported theme directory under themes/. It is written to a temporary file next to
    the target and published with os.replace so a failed run leaves no partial archive.
    """
    target = Path(output) if output is not None else default_backup_path(settings)
    target.parent.mkdir(parents=True, exist_ok=True)
    database = Database(settings.database)
    database.migrate()
    theme_names, theme_files = collect_themes(settings.theme_root)
    temporary = _temporary_path(target.parent, ".zip")
    snapshot = _temporary_path(target.parent, ".sqlite3")
    try:
        database.snapshot(snapshot)
        manifest = {
            "format": FORMAT_NAME,
            "format_version": FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "database": {"file": DATABASE_NAME, "schema_version": database.schema_version()},
            "themes": {"count": len(theme_names), "ids": theme_names},
        }
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            archive.write(snapshot, DATABASE_NAME)
            for path, arcname in theme_files:
                archive.write(path, arcname)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        snapshot.unlink(missing_ok=True)
    return target


def collect_themes(root: Path) -> tuple[list[str], list[tuple[Path, str]]]:
    """Return the theme directory ids and (file, archive path) pairs to back up."""
    if not root.is_dir():
        return [], []
    names = []
    files: list[tuple[Path, str]] = []
    for directory in sorted(root.iterdir(), key=lambda path: path.name):
        if directory.name.startswith(".") or directory.is_symlink() or not directory.is_dir():
            continue
        names.append(directory.name)
        for path in sorted(directory.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            files.append((path, f"{THEMES_PREFIX}/{relative}"))
    return names, files


def _temporary_path(directory: Path, suffix: str) -> Path:
    descriptor, name = mkstemp(dir=directory, prefix=TEMP_PREFIX, suffix=suffix)
    os.close(descriptor)
    return Path(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="备份知径数据库与已导入主题")
    parser.add_argument("--output", type=Path, help="备份 ZIP 路径，默认写入 <数据目录>/backups/")
    args = parser.parse_args(argv)
    target = create_backup(StudySettings(), args.output)
    print(f"备份已写入：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
