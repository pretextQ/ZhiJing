import hashlib
import io
import json
import os
import re
import struct
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, unquote

import pytest
from fastapi.testclient import TestClient

from zhijing.settings import Settings, StudySettings
from zhijing.main import create_app
from zhijing.services.themes import ThemeService

API = "/api/study/themes"
LOCAL = "http://127.0.0.1:18081"
DIGEST = ".archive-sha256"
MANIFEST = "theme.json"
MIB = 1024 * 1024
FIXTURES = Path(__file__).parent / "fixtures"
WEBM = (FIXTURES / "scene-loop.webm").read_bytes()


def png_bytes() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b"\x00\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


def webp_bytes() -> bytes:
    return b"RIFF" + struct.pack("<I", 4) + b"WEBP"


def mp3_bytes() -> bytes:
    return b"ID3\x04\x00\x00\x00\x00\x00\x00"


def mp3_frame_bytes() -> bytes:
    return b"\xff\xfb\x90\x00\x00\x00"


def ogg_bytes() -> bytes:
    return b"OggS\x00\x02\x00\x00"


def mp4_bytes() -> bytes:
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 24


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def manifest(**overrides) -> dict:
    data = {
        "schemaVersion": 1,
        "name": "合成主题",
        "background": "background.png",
        "cover": "cover.jpg",
        "ambient": "rain.mp3",
    }
    for key, value in overrides.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return data


def theme_zip(theme_manifest: dict | None = None, files: dict[str, bytes] | None = None) -> bytes:
    entries = {"background.png": png_bytes(), "cover.jpg": jpeg_bytes(), "rain.mp3": mp3_bytes()}
    entries.update(files or {})
    chosen = theme_manifest if theme_manifest is not None else manifest()
    entries[MANIFEST] = json.dumps(chosen, ensure_ascii=False).encode("utf-8")
    return zip_bytes(entries)


def client_at(tmp_path: Path, theme_dir: Path | None = None, **overrides) -> TestClient:
    settings = StudySettings(
        _env_file=None,
        database=tmp_path / "state" / "study.db",
        theme_dir=theme_dir,
        **overrides,
    )
    return TestClient(create_app(Settings(_env_file=None), settings), base_url=LOCAL)


def staging_entries(root: Path) -> list[Path]:
    return list(root.glob(".staging-*")) if root.is_dir() else []


def import_zip(api: TestClient, payload: bytes):
    return api.post(API, content=payload)


def parse_disposition(value: str) -> tuple[str, str]:
    match = re.fullmatch(r'attachment; filename="([^"]*)"; filename\*=UTF-8\'\'(.+)', value)
    assert match is not None, value
    return match.group(1), match.group(2)


def test_import_list_assets_and_delete_round_trip(tmp_path: Path):
    theme_root = tmp_path / "themes"
    payload = theme_zip()
    with client_at(tmp_path, theme_root) as api:
        assert api.get(API).json() == []
        response = import_zip(api, payload)
        assert response.status_code == 200, response.text
        card = response.json()
        assert set(card) == {
            "id",
            "name",
            "cover_url",
            "background_url",
            "ambient_url",
            "background_video_url",
        }
        assert re.fullmatch(r"[0-9a-f]{12}", card["id"])
        assert card["name"] == "合成主题"
        assert card["background_video_url"] is None
        base = f"{API}/{card['id']}/assets"
        assert card["background_url"] == f"{base}/background.png"
        assert card["cover_url"] == f"{base}/cover.jpg"
        assert card["ambient_url"] == f"{base}/rain.mp3"

        listing = api.get(API)
        assert listing.json() == [card]
        assert listing.headers["cache-control"] == "no-store"

        background = api.get(card["background_url"])
        assert background.status_code == 200
        assert background.content == png_bytes()
        assert background.headers["content-type"] == "image/png"
        assert background.headers["x-content-type-options"] == "nosniff"
        assert background.headers["cache-control"] == "no-store"
        assert api.get(card["cover_url"]).headers["content-type"] == "image/jpeg"
        assert api.get(card["ambient_url"]).headers["content-type"] == "audio/mpeg"

        directory = theme_root / card["id"]
        assert json.loads((directory / MANIFEST).read_text(encoding="utf-8")) == {
            "schemaVersion": 1,
            "name": "合成主题",
            "background": "background.png",
            "cover": "cover.jpg",
            "ambient": "rain.mp3",
        }
        assert (directory / DIGEST).read_text(encoding="ascii").strip() == hashlib.sha256(payload).hexdigest()
        assert (directory / "background.png").read_bytes() == png_bytes()
        assert staging_entries(theme_root) == []

        deleted = api.delete(f"{API}/{card['id']}")
        assert deleted.status_code == 204
        assert deleted.content == b""
        assert api.get(API).json() == []
        assert not (theme_root / card["id"]).exists()
        assert api.get(card["background_url"]).status_code == 404
        assert api.delete(f"{API}/{card['id']}").status_code == 404


def test_duplicate_upload_returns_the_existing_card(tmp_path: Path):
    theme_root = tmp_path / "themes"
    payload = theme_zip()
    with client_at(tmp_path, theme_root) as api:
        first = import_zip(api, payload)
        second = import_zip(api, payload)
        assert first.status_code == 200 and second.status_code == 200
        assert second.json() == first.json()
        assert api.get(API).json() == [first.json()]
        assert [path.name for path in theme_root.iterdir()] == [first.json()["id"]]
        assert staging_entries(theme_root) == []


def test_cover_falls_back_to_background_and_ambient_is_optional(tmp_path: Path):
    theme_root = tmp_path / "themes"
    chosen = {"schemaVersion": 1, "name": "极简主题", "background": "背景.png"}
    with client_at(tmp_path, theme_root) as api:
        payload = theme_zip(chosen, files={"背景.png": png_bytes()})
        card = import_zip(api, payload).json()
        assert card["name"] == "极简主题"
        assert card["cover_url"] == card["background_url"]
        assert card["ambient_url"] is None
        assert card["background_video_url"] is None
        encoded = quote("背景.png", safe="/")
        assert card["background_url"] == f"{API}/{card['id']}/assets/{encoded}"
        fetched = api.get(card["background_url"])
        assert fetched.status_code == 200
        assert fetched.content == png_bytes()
        assert (theme_root / card["id"] / "背景.png").is_file()
        stored = json.loads((theme_root / card["id"] / MANIFEST).read_text(encoding="utf-8"))
        assert "cover" not in stored and "ambient" not in stored and "backgroundVideo" not in stored
        assert api.get(f"{API}/{card['id']}/assets/cover.jpg").status_code == 404


def test_list_is_sorted_by_theme_id(tmp_path: Path):
    with client_at(tmp_path, tmp_path / "themes") as api:
        first = import_zip(api, theme_zip(manifest(name="甲主题"))).json()
        second = import_zip(api, theme_zip(manifest(name="乙主题"))).json()
        assert [card["id"] for card in api.get(API).json()] == sorted([first["id"], second["id"]])
        assert {card["name"] for card in api.get(API).json()} == {"甲主题", "乙主题"}


@pytest.mark.parametrize(
    "name,payload,expected",
    [
        ("background.png", png_bytes(), "image/png"),
        ("background.jpg", jpeg_bytes(), "image/jpeg"),
        ("background.jpeg", jpeg_bytes(), "image/jpeg"),
        ("background.webp", webp_bytes(), "image/webp"),
    ],
)
def test_supported_image_formats(tmp_path: Path, name: str, payload: bytes, expected: str):
    with client_at(tmp_path, tmp_path / "themes") as api:
        card = import_zip(api, theme_zip(manifest(background=name), files={name: payload})).json()
        response = api.get(card["background_url"])
        assert response.status_code == 200
        assert response.headers["content-type"] == expected


@pytest.mark.parametrize(
    "name,payload,expected",
    [
        ("rain.mp3", mp3_bytes(), "audio/mpeg"),
        ("rain.mp3", mp3_frame_bytes(), "audio/mpeg"),
        ("sea.ogg", ogg_bytes(), "audio/ogg"),
    ],
)
def test_supported_audio_formats(tmp_path: Path, name: str, payload: bytes, expected: str):
    with client_at(tmp_path, tmp_path / "themes") as api:
        card = import_zip(api, theme_zip(manifest(ambient=name), files={name: payload})).json()
        assert card["ambient_url"].endswith(f"/assets/{name}")
        response = api.get(card["ambient_url"])
        assert response.status_code == 200
        assert response.headers["content-type"] == expected


@pytest.mark.parametrize(
    "name,payload,expected",
    [
        ("loop.webm", WEBM, "video/webm"),
        ("loop.mp4", mp4_bytes(), "video/mp4"),
    ],
)
def test_supported_video_formats(tmp_path: Path, name: str, payload: bytes, expected: str):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(
            api, theme_zip(manifest(backgroundVideo=name), files={name: payload})
        ).json()
        assert card["background_video_url"] == f"{API}/{card['id']}/assets/{name}"
        response = api.get(card["background_video_url"])
        assert response.status_code == 200
        assert response.headers["content-type"] == expected
        assert response.content == payload
        assert response.headers["x-content-type-options"] == "nosniff"
        stored = json.loads((theme_root / card["id"] / MANIFEST).read_text(encoding="utf-8"))
        assert stored["backgroundVideo"] == name


def test_background_video_webm_matches_the_real_fixture(tmp_path: Path):
    theme_root = tmp_path / "themes"
    payload = theme_zip(manifest(backgroundVideo="video/scene-loop.webm"), files={"video/scene-loop.webm": WEBM})
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, payload).json()
        assert card["background_video_url"] == f"{API}/{card['id']}/assets/video/scene-loop.webm"
        response = api.get(card["background_video_url"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "video/webm"
        assert response.content == WEBM
        assert api.get(API).json() == [card]
        assert api.get(f"{API}/{card['id']}/export").status_code == 200


@pytest.mark.parametrize(
    "chosen,expected",
    [
        (manifest(background=None), "缺少背景图"),
        (manifest(schemaVersion=2), "版本"),
        (manifest(schemaVersion=None), "版本"),
        (manifest(name="   "), "名称"),
        (manifest(name="名" * 61), "名称"),
        (manifest(name=42), "名称"),
        (manifest(background="missing.png"), "不在主题包"),
        (manifest(background="../escape.png"), "路径不安全"),
        (manifest(background="/etc/passwd"), "路径不安全"),
        (manifest(background="..\\escape.png"), "路径不安全"),
        (manifest(cover=42), "cover"),
        (manifest(cover=""), "cover"),
        (manifest(ambient="missing.ogg"), "不在主题包"),
        (manifest(backgroundVideo=42), "backgroundVideo"),
        (manifest(backgroundVideo=""), "backgroundVideo"),
        (manifest(backgroundVideo="../loop.webm"), "路径不安全"),
        (manifest(backgroundVideo="missing.webm"), "不在主题包"),
    ],
)
def test_reject_invalid_manifests(tmp_path: Path, chosen: dict, expected: str):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        response = import_zip(api, theme_zip(chosen))
        assert response.status_code == 422, response.text
        assert expected in response.json()["detail"]
        assert api.get(API).json() == []
        assert staging_entries(theme_root) == []


@pytest.mark.parametrize(
    "chosen,files,expected",
    [
        (manifest(background="cover.jpg"), {"cover.jpg": b"not a jpeg"}, "不匹配"),
        (manifest(background="background.png"), {"background.png": b"not a png"}, "不匹配"),
        (manifest(ambient="rain.mp3"), {"rain.mp3": b"not audio"}, "不匹配"),
        (manifest(background="background.gif"), {"background.gif": b"GIF89a"}, "不支持的图片格式"),
        (manifest(ambient="rain.wav"), {"rain.wav": b"RIFF....WAVE"}, "不支持的音频格式"),
        (manifest(backgroundVideo="loop.webm"), {"loop.webm": b"not a webm"}, "不匹配"),
        (manifest(backgroundVideo="loop.mp4"), {"loop.mp4": b"not a mp4"}, "不匹配"),
        (manifest(backgroundVideo="loop.mov"), {"loop.mov": b"\x00\x00\x00\x14ftypqt  "}, "不支持的视频格式"),
    ],
)
def test_reject_media_with_wrong_content(tmp_path: Path, chosen: dict, files: dict[str, bytes], expected: str):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        response = import_zip(api, theme_zip(chosen, files=files))
        assert response.status_code == 422, response.text
        assert expected in response.json()["detail"]
        assert api.get(API).json() == []
        assert staging_entries(theme_root) == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"{not json", "不是有效的 JSON"),
        (b"[]", "JSON 对象"),
        (b"\xff\xfe\x00", "UTF-8"),
    ],
)
def test_reject_malformed_theme_json(tmp_path: Path, raw: bytes, expected: str):
    theme_root = tmp_path / "themes"
    payload = zip_bytes({
        MANIFEST: raw,
        "background.png": png_bytes(),
        "cover.jpg": jpeg_bytes(),
        "rain.mp3": mp3_bytes(),
    })
    with client_at(tmp_path, theme_root) as api:
        response = import_zip(api, payload)
        assert response.status_code == 422, response.text
        assert expected in response.json()["detail"]
        assert api.get(API).json() == []
        assert staging_entries(theme_root) == []


def test_manifest_must_be_in_archive_root(tmp_path: Path):
    theme_root = tmp_path / "themes"
    payload = zip_bytes({
        f"nested/{MANIFEST}": json.dumps(manifest()).encode("utf-8"),
        "background.png": png_bytes(),
        "cover.jpg": jpeg_bytes(),
        "rain.mp3": mp3_bytes(),
    })
    with client_at(tmp_path, theme_root) as api:
        response = import_zip(api, payload)
        assert response.status_code == 422
        assert "根目录缺少 theme.json" in response.json()["detail"]


@pytest.mark.parametrize(
    "name",
    ["../escape.txt", "/absolute.txt", "C:/drive.txt", "..\\backslash.txt", "assets/../../escape.txt"],
)
def test_reject_unsafe_archive_entries(tmp_path: Path, name: str):
    theme_root = tmp_path / "themes"
    payload = zip_bytes({
        MANIFEST: json.dumps(manifest(), ensure_ascii=False).encode("utf-8"),
        "background.png": png_bytes(),
        "cover.jpg": jpeg_bytes(),
        "rain.mp3": mp3_bytes(),
        name: b"synthetic extra",
    })
    with client_at(tmp_path, theme_root) as api:
        response = import_zip(api, payload)
        assert response.status_code == 422, response.text
        assert "路径不安全" in response.json()["detail"]
        assert api.get(API).json() == []
        assert staging_entries(theme_root) == []


def test_reject_symlink_entries(tmp_path: Path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(MANIFEST, json.dumps(manifest(), ensure_ascii=False).encode("utf-8"))
        archive.writestr("background.png", png_bytes())
        archive.writestr("cover.jpg", jpeg_bytes())
        archive.writestr("rain.mp3", mp3_bytes())
        link = zipfile.ZipInfo("link.png")
        link.external_attr = 0o120777 << 16
        archive.writestr(link, b"background.png")
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        response = import_zip(api, buffer.getvalue())
        assert response.status_code == 422
        assert "符号链接" in response.json()["detail"]
        assert api.get(API).json() == []


def test_reject_encrypted_entries(tmp_path: Path):
    payload = bytearray(theme_zip())
    offset = payload.index(b"PK\x01\x02") + 8
    payload[offset] |= 0x01
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        response = import_zip(api, bytes(payload))
        assert response.status_code == 422
        assert "加密" in response.json()["detail"]
        assert api.get(API).json() == []


def test_archive_size_limit_returns_413_with_configured_text(tmp_path: Path):
    theme_root = tmp_path / "themes"
    payload = theme_zip(files={"noise.bin": os.urandom(MIB + 128 * 1024)})
    with client_at(tmp_path, theme_root, theme_max_archive_mb=1) as api:
        response = import_zip(api, payload)
        assert response.status_code == 413, response.text
        assert response.json()["detail"] == "主题包不能超过 1 MiB"
        assert api.get(API).json() == []
        assert staging_entries(theme_root) == []


def test_expanded_size_limit_counts_background_video(tmp_path: Path):
    theme_root = tmp_path / "themes"
    video = b"\x1aE\xdf\xa3" + os.urandom(MIB + 128 * 1024)
    payload = theme_zip(manifest(backgroundVideo="loop.webm"), files={"loop.webm": video})
    with client_at(tmp_path, theme_root, theme_max_expanded_mb=1) as api:
        response = import_zip(api, payload)
        assert response.status_code == 422, response.text
        assert response.json()["detail"] == "主题包解压后不能超过 1 MiB"
        assert api.get(API).json() == []
        assert staging_entries(theme_root) == []


def test_entry_limit_uses_configured_value(tmp_path: Path):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root, theme_max_entries=3) as api:
        response = import_zip(api, theme_zip())
        assert response.status_code == 422, response.text
        assert response.json()["detail"] == "主题包不能超过 3 个文件"
        assert api.get(API).json() == []
        assert staging_entries(theme_root) == []


def test_reject_invalid_archives_and_empty_upload(tmp_path: Path):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        broken = import_zip(api, b"not a zip")
        assert broken.status_code == 422
        assert "ZIP" in broken.json()["detail"]
        empty = import_zip(api, b"")
        assert empty.status_code == 422
        assert "不能为空" in empty.json()["detail"]
        assert api.get(API).json() == []


def test_assets_only_serve_files_referenced_by_the_manifest(tmp_path: Path):
    theme_root = tmp_path / "themes"
    extras = {
        "extra.txt": b"synthetic extra",
        "assets/note.txt": b"synthetic nested",
        "loop.webm": WEBM,
    }
    payload = theme_zip(manifest(backgroundVideo="loop.webm"), files=extras)
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, payload).json()
        base = f"{API}/{card['id']}/assets"
        assert api.get(card["background_video_url"]).status_code == 200
        for path in ("extra.txt", MANIFEST, DIGEST, "assets/note.txt", "missing.png", "loop.mp4"):
            assert api.get(f"{base}/{path}").status_code == 404
        for path in ("..%2Ftheme.json", "%2e%2e%2Ftheme.json", "..%2F..%2Fstate%2Fstudy.db"):
            assert api.get(f"{base}/{path}").status_code == 404
        for theme_id in ("unknown", "A" * 12, "0" * 12, "0123456789abc"):
            assert api.get(f"{API}/{theme_id}/assets/background.png").status_code == 404
            assert api.delete(f"{API}/{theme_id}").status_code == 404


def test_access_control_matches_study_api(tmp_path: Path):
    theme_root = tmp_path / "themes"
    payload = theme_zip()
    with client_at(tmp_path, theme_root) as api:
        assert api.get(API, headers={"Host": "outside.example"}).status_code == 403
        assert import_zip(api, payload).status_code == 200
        card = api.get(API).json()[0]
        assert api.post(API, content=payload, headers={"Host": "outside.example"}).status_code == 403
        assert api.post(
            API, content=theme_zip(manifest(name="外站主题")), headers={"Origin": "https://outside.example"}
        ).status_code == 403
        assert api.get(API).json() == [card]
        assert api.patch(
            f"{API}/{card['id']}", json={"name": "外站改名"}, headers={"Host": "outside.example"}
        ).status_code == 403
        assert api.get(f"{API}/{card['id']}/export", headers={"Host": "outside.example"}).status_code == 403
        assert api.get(f"{API}/limits", headers={"Host": "outside.example"}).status_code == 403
        assert api.get(f"{API}/limits").status_code == 200
        assert api.get(API).json() == [card]
        assert api.post(API, content=theme_zip(manifest(name="同源主题")), headers={"Origin": LOCAL}).status_code == 200
        assert api.get(API).headers["cache-control"] == "no-store"
        assert api.get(API, headers={"Host": "localhost:18081"}).status_code == 200
        assert api.delete(f"{API}/{card['id']}", headers={"Origin": "http://127.0.0.1:9999"}).status_code == 403
        assert api.get(
            card["background_url"], headers={"Host": "outside.example"}
        ).status_code == 403
        assert api.delete(f"{API}/{card['id']}").status_code == 204


def test_theme_dir_injection_and_default_root(tmp_path: Path):
    injected = tmp_path / "custom-themes"
    with client_at(tmp_path, injected) as api:
        card = import_zip(api, theme_zip()).json()
    assert (injected / card["id"] / MANIFEST).is_file()
    assert not (tmp_path / "state" / "themes").exists()

    with client_at(tmp_path) as api:
        card = import_zip(api, theme_zip()).json()
    default_root = tmp_path / "state" / "themes"
    assert (default_root / card["id"] / MANIFEST).is_file()

    assert ThemeService(StudySettings(_env_file=None, database=tmp_path / "db" / "study.db")).root == (
        tmp_path / "db" / "themes"
    )
    assert ThemeService(
        StudySettings(_env_file=None, database=tmp_path / "db" / "study.db", theme_dir=injected)
    ).root == injected


def test_imported_themes_survive_a_new_app_instance(tmp_path: Path):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, theme_zip()).json()
    with client_at(tmp_path, theme_root) as api:
        assert api.get(API).json() == [card]
        assert api.get(card["background_url"]).content == png_bytes()
        assert api.delete(f"{API}/{card['id']}").status_code == 204


def test_failed_import_leaves_no_partial_theme(tmp_path: Path):
    theme_root = tmp_path / "themes"
    payload = theme_zip(manifest(background="missing.png"))
    with client_at(tmp_path, theme_root) as api:
        response = import_zip(api, payload)
        assert response.status_code == 422
        assert api.get(API).json() == []
        assert list(theme_root.iterdir()) == []


def test_concurrent_identical_imports_publish_one_theme(tmp_path: Path):
    store = ThemeService(
        StudySettings(
            _env_file=None,
            database=tmp_path / "state" / "study.db",
            theme_dir=tmp_path / "themes",
        )
    )
    payload = theme_zip()
    with ThreadPoolExecutor(max_workers=8) as pool:
        cards = list(pool.map(lambda _: store.import_archive(payload), range(8)))
    assert len({card.id for card in cards}) == 1
    assert len(store.cards()) == 1
    assert staging_entries(tmp_path / "themes") == []


def test_delete_only_removes_the_selected_theme(tmp_path: Path):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        first = import_zip(api, theme_zip(manifest(name="保留主题"))).json()
        second = import_zip(api, theme_zip(manifest(name="删除主题"))).json()
        assert api.delete(f"{API}/{second['id']}").status_code == 204
        assert api.get(API).json() == [first]
        assert api.get(first["background_url"]).status_code == 200
        assert api.get(second["background_url"]).status_code == 404
        assert [path.name for path in theme_root.iterdir()] == [first["id"]]


def test_rename_theme_updates_card_manifest_and_duplicate_import(tmp_path: Path):
    theme_root = tmp_path / "themes"
    payload = theme_zip(manifest(backgroundVideo="loop.webm"), files={"loop.webm": WEBM})
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, payload).json()
        response = api.patch(f"{API}/{card['id']}", json={"name": "  新名字  "})
        assert response.status_code == 200, response.text
        renamed = response.json()
        assert renamed["name"] == "新名字"
        assert renamed["id"] == card["id"]
        assert {key: value for key, value in renamed.items() if key != "name"} == {
            key: value for key, value in card.items() if key != "name"
        }
        assert api.get(API).json() == [renamed]

        directory = theme_root / card["id"]
        assert json.loads((directory / MANIFEST).read_text(encoding="utf-8")) == {
            "schemaVersion": 1,
            "name": "新名字",
            "background": "background.png",
            "cover": "cover.jpg",
            "backgroundVideo": "loop.webm",
            "ambient": "rain.mp3",
        }
        assert (directory / DIGEST).read_text(encoding="ascii").strip() == hashlib.sha256(payload).hexdigest()
        assert api.get(renamed["background_video_url"]).status_code == 200

        duplicate = import_zip(api, payload)
        assert duplicate.status_code == 200
        assert duplicate.json() == renamed
        assert [path.name for path in theme_root.iterdir()] == [card["id"]]
        assert staging_entries(theme_root) == []


def test_rename_accepts_the_documented_boundaries(tmp_path: Path):
    with client_at(tmp_path, tmp_path / "themes") as api:
        card = import_zip(api, theme_zip()).json()
        longest = "名" * 60
        response = api.patch(f"{API}/{card['id']}", json={"name": longest})
        assert response.status_code == 200, response.text
        assert response.json()["name"] == longest
        assert api.patch(f"{API}/{card['id']}", json={"name": "  abc  "}).json()["name"] == "abc"


def test_renamed_theme_survives_a_new_app_instance(tmp_path: Path):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, theme_zip()).json()
        assert api.patch(f"{API}/{card['id']}", json={"name": "重启后主题"}).status_code == 200
    with client_at(tmp_path, theme_root) as api:
        cards = api.get(API).json()
        assert [entry["name"] for entry in cards] == ["重启后主题"]
        response = api.get(f"{API}/{card['id']}/export")
        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert json.loads(archive.read(MANIFEST).decode("utf-8"))["name"] == "重启后主题"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "名" * 61},
        {"name": 42},
        {"name": None},
        {"name": ["不是字符串"]},
        {},
    ],
)
def test_rename_rejects_invalid_names(tmp_path: Path, payload: dict):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, theme_zip()).json()
        response = api.patch(f"{API}/{card['id']}", json=payload)
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert isinstance(detail, str) and "主题名称" in detail
        assert api.get(API).json() == [card]
        assert json.loads((theme_root / card["id"] / MANIFEST).read_text(encoding="utf-8"))["name"] == "合成主题"


@pytest.mark.parametrize("theme_id", ["unknown", "A" * 12, "0" * 12, "0123456789abc"])
def test_rename_unknown_theme_returns_404(tmp_path: Path, theme_id: str):
    with client_at(tmp_path, tmp_path / "themes") as api:
        response = api.patch(f"{API}/{theme_id}", json={"name": "新名字"})
        assert response.status_code == 404
        assert response.json()["detail"] == "找不到这个主题"


def test_export_archive_contains_manifest_and_assets(tmp_path: Path):
    theme_root = tmp_path / "themes"
    payload = theme_zip(manifest(backgroundVideo="loop.webm"), files={"loop.webm": WEBM})
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, payload).json()
        response = api.get(f"{API}/{card['id']}/export")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/zip"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        disposition = response.headers["content-disposition"]
        disposition.encode("latin-1")
        fallback, encoded = parse_disposition(disposition)
        assert fallback == "theme.zip"
        assert encoded == quote("合成主题.zip", safe="")
        assert unquote(encoded) == "合成主题.zip"

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.namelist() == [
                MANIFEST,
                "background.png",
                "cover.jpg",
                "loop.webm",
                "rain.mp3",
            ]
            assert DIGEST not in archive.namelist()
            assert archive.testzip() is None
            saved = json.loads(archive.read(MANIFEST).decode("utf-8"))
            assert saved == {
                "schemaVersion": 1,
                "name": "合成主题",
                "background": "background.png",
                "cover": "cover.jpg",
                "backgroundVideo": "loop.webm",
                "ambient": "rain.mp3",
            }
            assert archive.read("background.png") == png_bytes()
            assert archive.read("cover.jpg") == jpeg_bytes()
            assert archive.read("loop.webm") == WEBM
            assert archive.read("rain.mp3") == mp3_bytes()


def test_export_uses_the_renamed_theme_name(tmp_path: Path):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, theme_zip()).json()
        assert api.patch(f"{API}/{card['id']}", json={"name": "我的书桌"}).status_code == 200
        response = api.get(f"{API}/{card['id']}/export")
        assert response.status_code == 200
        fallback, encoded = parse_disposition(response.headers["content-disposition"])
        assert fallback == "theme.zip"
        assert unquote(encoded) == "我的书桌.zip"
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert json.loads(archive.read(MANIFEST).decode("utf-8"))["name"] == "我的书桌"


def test_export_preserves_nested_paths_and_deduplicates_references(tmp_path: Path):
    theme_root = tmp_path / "themes"
    chosen = {
        "schemaVersion": 1,
        "name": "嵌套主题",
        "background": "assets/背景.png",
        "cover": "assets/背景.png",
    }
    payload = theme_zip(chosen, files={"assets/背景.png": png_bytes()})
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, payload).json()
        response = api.get(f"{API}/{card['id']}/export")
        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.namelist() == [MANIFEST, "assets/背景.png"]
            assert json.loads(archive.read(MANIFEST).decode("utf-8")) == chosen
            assert archive.read("assets/背景.png") == png_bytes()
        fallback, encoded = parse_disposition(response.headers["content-disposition"])
        assert fallback == "theme.zip"
        assert unquote(encoded) == "嵌套主题.zip"


def test_export_ascii_fallback_sanitizes_the_name(tmp_path: Path):
    theme_root = tmp_path / "themes"
    weird = 'A"B/C\\D 主题'
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, theme_zip()).json()
        assert api.patch(f"{API}/{card['id']}", json={"name": weird}).status_code == 200
        response = api.get(f"{API}/{card['id']}/export")
        assert response.status_code == 200
        disposition = response.headers["content-disposition"]
        disposition.encode("latin-1")
        fallback, encoded = parse_disposition(disposition)
        assert fallback == "ABCD.zip"
        assert fallback.isascii() and '"' not in fallback and "/" not in fallback and "\\" not in fallback
        assert unquote(encoded) == f"{weird}.zip"


@pytest.mark.parametrize("theme_id", ["unknown", "A" * 12, "0" * 12, "0123456789abc"])
def test_export_unknown_theme_returns_404(tmp_path: Path, theme_id: str):
    with client_at(tmp_path, tmp_path / "themes") as api:
        response = api.get(f"{API}/{theme_id}/export")
        assert response.status_code == 404
        assert response.json()["detail"] == "找不到这个主题"


def test_export_missing_asset_returns_409(tmp_path: Path):
    theme_root = tmp_path / "themes"
    with client_at(tmp_path, theme_root) as api:
        card = import_zip(api, theme_zip()).json()
        (theme_root / card["id"] / "cover.jpg").unlink()
        response = api.get(f"{API}/{card['id']}/export")
        assert response.status_code == 409
        assert "缺失" in response.json()["detail"]


def test_limits_default_to_the_documented_values(tmp_path: Path, monkeypatch):
    for key in (
        "ZHIJING_STUDY_THEME_MAX_ARCHIVE_MB",
        "ZHIJING_STUDY_THEME_MAX_EXPANDED_MB",
        "ZHIJING_STUDY_THEME_MAX_ENTRIES",
    ):
        monkeypatch.delenv(key, raising=False)
    with client_at(tmp_path, tmp_path / "themes") as api:
        response = api.get(f"{API}/limits")
        assert response.status_code == 200
        assert response.json() == {"max_archive_mb": 32, "max_expanded_mb": 64, "max_entries": 32}
        assert response.headers["cache-control"] == "no-store"


def test_limits_follow_settings_and_environment(tmp_path: Path, monkeypatch):
    for key in (
        "ZHIJING_STUDY_THEME_MAX_ARCHIVE_MB",
        "ZHIJING_STUDY_THEME_MAX_EXPANDED_MB",
        "ZHIJING_STUDY_THEME_MAX_ENTRIES",
    ):
        monkeypatch.delenv(key, raising=False)
    with client_at(
        tmp_path,
        tmp_path / "themes",
        theme_max_archive_mb=2,
        theme_max_expanded_mb=3,
        theme_max_entries=5,
    ) as api:
        assert api.get(f"{API}/limits").json() == {
            "max_archive_mb": 2,
            "max_expanded_mb": 3,
            "max_entries": 5,
        }
    monkeypatch.setenv("ZHIJING_STUDY_THEME_MAX_ARCHIVE_MB", "2")
    monkeypatch.setenv("ZHIJING_STUDY_THEME_MAX_EXPANDED_MB", "3")
    monkeypatch.setenv("ZHIJING_STUDY_THEME_MAX_ENTRIES", "5")
    with client_at(tmp_path, tmp_path / "themes") as api:
        assert api.get(f"{API}/limits").json() == {
            "max_archive_mb": 2,
            "max_expanded_mb": 3,
            "max_entries": 5,
        }


def test_store_uses_configured_limits(tmp_path: Path):
    store = ThemeService(
        StudySettings(
            _env_file=None,
            database=tmp_path / "db" / "study.db",
            theme_max_archive_mb=2,
            theme_max_expanded_mb=3,
            theme_max_entries=5,
        )
    )
    assert store.max_archive_bytes == 2 * MIB
    assert store.max_expanded_bytes == 3 * MIB
    assert store.max_entries == 5
    assert store.limits().model_dump() == {
        "max_archive_mb": 2,
        "max_expanded_mb": 3,
        "max_entries": 5,
    }


def test_configured_limits_allow_boundary_imports(tmp_path: Path):
    with client_at(
        tmp_path,
        tmp_path / "themes",
        theme_max_archive_mb=1,
        theme_max_expanded_mb=1,
        theme_max_entries=4,
    ) as api:
        assert api.get(f"{API}/limits").json() == {
            "max_archive_mb": 1,
            "max_expanded_mb": 1,
            "max_entries": 4,
        }
        response = import_zip(api, theme_zip())
        assert response.status_code == 200, response.text
        assert api.get(API).json() == [response.json()]
