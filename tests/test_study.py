from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from zhijing.settings import Settings, StudySettings
from zhijing.main import create_app
from zhijing import main
from zhijing.services import study

API = "/api/study"
LOCAL = "http://127.0.0.1:18081"
VIDEO = "https://www.bilibili.com/video/BV1abc123XYZ/"
SECOND = "https://m.bilibili.com/video/av12345/"
NOTE = "## 合成笔记\n\n保留 Markdown 与公式 $x^2$。"


def client_at(tmp_path: Path, obsidian_dir: Path | None = None) -> TestClient:
    app = create_app(
        Settings(_env_file=None),
        StudySettings(_env_file=None, database=tmp_path / "state" / "study.db", obsidian_dir=obsidian_dir),
    )
    return TestClient(app, base_url=LOCAL)


def open_link(api: TestClient, url: str = VIDEO):
    response = api.post(f"{API}/lessons", json={"url": url})
    assert response.status_code == 200, response.text
    return response.json()


def test_reopen_preserves_each_part_and_draft_across_instances(tmp_path: Path):
    with client_at(tmp_path) as api:
        assert api.get(API).json() == {"lessons": [], "active": None, "obsidian_enabled": False}
        first = open_link(api)
        part = open_link(api, f"{VIDEO}?p=2&t=41&spm_id_from=synthetic")
        assert first["id"] != part["id"]
        assert part["part"] == 2 and part["seconds"] == 41
        assert part["original_url"] == f"{VIDEO}?p=2"
        assert "p=2&danmaku=0" in part["embed_url"]
        lesson = f"{API}/lessons/{part['id']}"
        assert api.patch(lesson, json={"seconds": 754, "title": "合成课程"}).status_code == 200
        assert api.put(lesson + "/note", json={"markdown": NOTE, "revision": 0}).json() == {"revision": 1}
        assert open_link(api, f"{VIDEO}?p=2")["seconds"] == 754
    with client_at(tmp_path) as api:
        room = api.get(API).json()
        assert [item["id"] for item in room["lessons"]] == [part["id"], first["id"]]
        assert room["active"]["markdown"] == NOTE
        assert room["active"]["title"] == "合成课程"
        assert room["active"]["seconds"] == 754
        assert api.post(f"{API}/lessons/{first['id']}/open").json()["markdown"] == ""
        assert api.get(API).json()["active"]["id"] == first["id"]


def test_note_save_retries_and_detects_stale_drafts(tmp_path: Path):
    with client_at(tmp_path) as api:
        item = open_link(api)
        url = f"{API}/lessons/{item['id']}/note"
        payload = {"markdown": NOTE, "revision": 0}
        assert api.put(url, json=payload).json() == {"revision": 1}
        assert api.put(url, json=payload).json() == {"revision": 1}
        assert api.put(url, json={"markdown": "另一份草稿", "revision": 0}).status_code == 409
        assert api.get(API).json()["active"]["markdown"] == NOTE
        assert api.put(url, json={"markdown": "", "revision": 1}).json() == {"revision": 2}


def test_obsidian_updates_only_documents_it_has_written(tmp_path: Path):
    vault = tmp_path / "synthetic-vault"
    vault.mkdir()
    with client_at(tmp_path, vault) as api:
        item = open_link(api)
        url = f"{API}/lessons/{item['id']}"
        assert api.put(url + "/note", json={"markdown": NOTE, "revision": 0}).status_code == 200
        saved = api.post(url + "/export", json={"revision": 1})
        assert saved.status_code == 200
        target = vault / saved.json()["filename"]
        assert f"[在 B 站打开]({VIDEO}?p=1)" in target.read_text(encoding="utf-8")
        assert NOTE in target.read_text(encoding="utf-8")

        updated = NOTE + "\n\n续写"
        assert api.put(url + "/note", json={"markdown": updated, "revision": 1}).status_code == 200
        assert api.post(url + "/export", json={"revision": 2}).status_code == 200
        assert updated in target.read_text(encoding="utf-8")

        target.write_text("Obsidian 中新增的合成内容", encoding="utf-8")
        assert api.post(url + "/export", json={"revision": 2}).status_code == 409
        assert target.read_text(encoding="utf-8") == "Obsidian 中新增的合成内容"
        assert not list(vault.glob(".zhijing-*"))


@pytest.mark.parametrize("url", [
    "https://www.bilibili.com.example/video/BV1abc123XYZ/",
    "https://example.com@www.bilibili.com/video/BV1abc123XYZ/",
    f"{VIDEO}?p=0",
    f"{VIDEO}?t=-1",
])
def test_reject_unrecognized_hosts_and_invalid_parts(tmp_path: Path, url: str):
    with client_at(tmp_path) as api:
        response = api.post(f"{API}/lessons", json={"url": url})
        assert response.status_code == 422
        assert api.get(API).json()["lessons"] == []


def test_short_link_accepts_b_station_target_without_following_other_hosts(tmp_path: Path, monkeypatch):
    def respond(url, **kwargs):
        assert url == "https://b23.tv/synthetic"
        assert kwargs["follow_redirects"] is False
        return httpx.Response(302, headers={"Location": respond.target})

    respond.target = SECOND + "?p=3"
    monkeypatch.setattr(study.httpx, "get", respond)
    with client_at(tmp_path) as api:
        item = open_link(api, "https://b23.tv/synthetic?t=60")
        assert item["embed_url"].endswith("?aid=12345&p=3&danmaku=0&autoplay=0")
        assert item["seconds"] == 60
        respond.target = "http://127.0.0.1:12345/"
        assert api.post(f"{API}/lessons", json={"url": "https://b23.tv/synthetic"}).status_code == 422


def test_courses_without_embed_keep_their_original_link(tmp_path: Path):
    with client_at(tmp_path) as api:
        url = "https://www.bilibili.com/cheese/play/ep12345/"
        item = open_link(api, url)
        assert item["original_url"] == url
        assert item["embed_url"] is None
        assert api.put(
            f"{API}/lessons/{item['id']}/note", json={"markdown": NOTE, "revision": 0},
        ).status_code == 200


def test_study_api_accepts_local_requests_and_rejects_other_web_origins(tmp_path: Path):
    with client_at(tmp_path) as api:
        assert api.get(API, headers={"Host": "outside.example"}).status_code == 403
        payload = {"url": VIDEO}
        assert api.post(f"{API}/lessons", json=payload, headers={"Origin": "https://outside.example"}).status_code == 403
        assert api.post(f"{API}/lessons", json=payload, headers={"Origin": LOCAL}).status_code == 200


def test_room_and_course_workspace_can_be_opened_directly(tmp_path: Path, monkeypatch):
    frontend = tmp_path / "site"
    frontend.mkdir()
    frontend.joinpath("index.html").write_text("<title>合成自习室</title>", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND", frontend)
    with client_at(tmp_path) as api:
        for path in ("/", "/courses"):
            assert api.get(path).text == "<title>合成自习室</title>"
        assert api.get(API).status_code == 200
