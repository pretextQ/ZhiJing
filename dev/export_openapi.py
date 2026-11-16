"""Export the FastAPI OpenAPI schema for TypeScript type generation.

Usage:
    uv run --locked --no-sync python dev/export_openapi.py
    npm.cmd --prefix frontend run gen:api
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from zhijing.main import app  # noqa: E402


def main() -> None:
    target = ROOT / "frontend" / "openapi.json"
    schema = app.openapi()
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths = len(schema.get("paths", {}))
    schemas = len(schema.get("components", {}).get("schemas", {}))
    print(f"wrote {target.relative_to(ROOT)} ({paths} paths, {schemas} schemas)")


if __name__ == "__main__":
    main()
