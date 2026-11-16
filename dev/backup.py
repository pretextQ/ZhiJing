"""Create a ZIP backup of the Zhijing data directory.

Usage:
    uv run --locked --no-sync python dev/backup.py
    uv run --locked --no-sync python dev/backup.py --output D:\backups\zhijing.zip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from zhijing.backup import create_backup  # noqa: E402
from zhijing.settings import StudySettings  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="备份知径数据库与已导入主题")
    parser.add_argument("--output", type=Path, help="备份 ZIP 路径，默认写入 <数据目录>/backups/")
    args = parser.parse_args(argv)
    settings = StudySettings()
    target = create_backup(settings, args.output)
    print(f"备份已写入：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
