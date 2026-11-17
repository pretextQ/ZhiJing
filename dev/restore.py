"""Restore a Zhijing backup archive into the data directory.

Usage:
    uv run --locked --no-sync python dev/restore.py backup.zip --inspect
    uv run --locked --no-sync python dev/restore.py backup.zip --force
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from zhijing.restore import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
