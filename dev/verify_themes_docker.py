"""Docker acceptance for theme-pack persistence.

Builds the image with an isolated compose project and port, imports a synthetic
theme pack, recreates the container on the same volume, and verifies that the
theme card and its assets survive. Run from the repository root:

    uv run --locked --no-sync python dev/verify_themes_docker.py

The script always tries to remove the test project and its volume at the end.
"""

from __future__ import annotations

import io
import json
import os
import struct
import subprocess
import time
import zipfile
import zlib
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "zhijing-theme-qa"
PORT = "18129"
BASE = f"http://127.0.0.1:{PORT}"
ENV = os.environ | {"ZHIJING_DOCKER_PORT": PORT}
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-p", PROJECT]


def compose(*args: str) -> None:
    subprocess.run([*COMPOSE, *args], cwd=ROOT, env=ENV, check=True)


def make_png(width: int = 16, height: int = 8) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes((40, 90, 70)) * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def make_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("theme.json", json.dumps({
            "schemaVersion": 1,
            "name": "Docker 合成主题",
            "background": "background.png",
            "cover": "cover.png",
            "ambient": "rain.mp3",
        }, ensure_ascii=False))
        archive.writestr("background.png", make_png(24, 8))
        archive.writestr("cover.png", make_png(12, 4))
        archive.writestr("rain.mp3", (bytes([0xFF, 0xFB, 0x90, 0x00]) + b"\x00" * 413) * 80)
    return buffer.getvalue()


def wait_ready(timeout: float = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(BASE + "/", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("Docker instance did not become ready")


def themes(client: httpx.Client) -> list[dict]:
    response = client.get(BASE + "/api/study/themes")
    assert response.status_code == 200, response.text
    return response.json()


def main() -> None:
    archive = make_zip()
    try:
        compose("up", "-d", "--build", "--wait")
        wait_ready()
        with httpx.Client(timeout=20, trust_env=False) as client:
            assert themes(client) == []
            imported = client.post(BASE + "/api/study/themes", content=archive,
                                   headers={"Content-Type": "application/zip"})
            assert imported.status_code == 200, imported.text
            card = imported.json()
            theme_id = card["id"]
            assert card["name"] == "Docker 合成主题" and theme_id
            assert card["ambient_url"].endswith("rain.mp3")
            duplicate = client.post(BASE + "/api/study/themes", content=archive,
                                    headers={"Content-Type": "application/zip"})
            assert duplicate.status_code == 200 and duplicate.json()["id"] == theme_id
            background = client.get(BASE + card["background_url"])
            assert background.status_code == 200 and background.headers["content-type"] == "image/png"
            assert background.content.startswith(b"\x89PNG")
            ambient = client.get(BASE + card["ambient_url"])
            assert ambient.status_code == 200 and ambient.headers["content-type"] == "audio/mpeg"
            print(f"PASS docker import: {theme_id} with background and ambient assets")

            broken = io.BytesIO()
            with zipfile.ZipFile(broken, "w") as archive_file:
                archive_file.writestr("theme.json", json.dumps({"schemaVersion": 1, "name": "缺背景"}))
            invalid = client.post(BASE + "/api/study/themes", content=broken.getvalue(),
                                  headers={"Content-Type": "application/zip"})
            assert invalid.status_code == 422 and "背景" in invalid.json()["detail"], invalid.text
            print("PASS docker invalid pack: 422 with Chinese reason")

        compose("up", "-d", "--force-recreate", "--wait")
        wait_ready()
        with httpx.Client(timeout=20, trust_env=False) as client:
            recreated = themes(client)
            assert [item["id"] for item in recreated] == [theme_id], recreated
            background = client.get(BASE + card["background_url"])
            assert background.status_code == 200 and background.headers["content-type"] == "image/png"
            deleted = client.delete(BASE + f"/api/study/themes/{theme_id}")
            assert deleted.status_code == 204, deleted.text
            assert themes(client) == []
            print("PASS docker recreate: theme and assets survived; delete leaves an empty library")
    finally:
        compose("down", "-v")


if __name__ == "__main__":
    main()
