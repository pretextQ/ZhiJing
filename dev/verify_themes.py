"""Browser acceptance for the ZhiJing scene and theme-pack feature.

Prerequisites:
    npm.cmd --prefix frontend run build
    uv pip install --target .dev/browser-deps playwright==1.65.2
    $env:PYTHONPATH = (Resolve-Path .dev/browser-deps).Path
    uv run --locked --no-sync python -m playwright install chromium

Run:
    $env:PYTHONPATH = (Resolve-Path .dev/browser-deps).Path
    uv run --locked --no-sync python dev/verify_themes.py
"""

from __future__ import annotations

import io
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:18127"
BUILTINS = ["rain", "library", "morning", "seaside", "train", "pixel"]
BUILTIN_NAMES = ["雨窗", "夜间图书馆", "清晨书桌", "海边木屋", "暮色列车", "像素夏夜"]
VIDEO = (ROOT / "tests" / "fixtures" / "scene-loop.webm").read_bytes()


def make_png(width: int = 12, height: int = 12, color=(58, 104, 82)) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(color) * width for _ in range(height))
    return header + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def make_mp3() -> bytes:
    # 80 silent MPEG-1 Layer III frames; Chromium/Edge decode this as ~2s of silence.
    frame = bytes([0xFF, 0xFB, 0x90, 0x00]) + b"\x00" * 413
    return frame * 80


def make_zip(
    name: str, *, background: bool = True, cover: bool = True, ambient: bool = True, video: bool = True
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        manifest = {"schemaVersion": 1, "name": name}
        if background:
            manifest["background"] = "assets/background.png"
        if cover:
            manifest["cover"] = "assets/cover.png"
        if ambient:
            manifest["ambient"] = "audio/rain.mp3"
        if video:
            manifest["backgroundVideo"] = "assets/loop.webm"
        archive.writestr("theme.json", json.dumps(manifest, ensure_ascii=False))
        if background:
            archive.writestr("assets/background.png", make_png(24, 8))
        if cover:
            archive.writestr("assets/cover.png", make_png(12, 4, (90, 110, 70)))
        if ambient:
            archive.writestr("audio/rain.mp3", make_mp3())
        if video:
            archive.writestr("assets/loop.webm", VIDEO)
    return buffer.getvalue()


def wait_service(base: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            if httpx.get(base + "/api/study", timeout=0.5).is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError("FastAPI test service did not start")


def backdrop_style(page) -> str:
    return page.locator(".focus-backdrop").get_attribute("style") or ""


def backdrop_class(page) -> str:
    return page.locator(".focus-backdrop").get_attribute("class") or ""


def saved_motion(page):
    return page.evaluate("JSON.parse(localStorage.getItem('zhijing:motion') || 'null')")


def saved_scene(page):
    return page.evaluate("JSON.parse(localStorage.getItem('zhijing:scene') || 'null')")


def card(page, theme_id: str):
    clickable = page.locator(f'button[data-theme-id="{theme_id}"]')
    return clickable.first if clickable.count() else page.locator(f'[data-theme-id="{theme_id}"]').first


def grid_columns(page, panel) -> int:
    boxes = []
    for item in panel.locator("[data-theme-id]").all():
        box = item.bounding_box()
        if box:
            boxes.append(round(box["x"]))
    return len(set(boxes))


def open_scenes(page, panel):
    trigger = page.get_by_role("button", name=re.compile("切换场景"))
    trigger.click()
    expect(panel).to_be_visible()
    expect(panel.get_by_role("heading", name="选择场景")).to_be_visible()
    expect(panel.locator("[data-theme-id]")).to_have_count(6)
    return trigger


def run() -> None:
    errors: list[str] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception:
            browser = playwright.chromium.launch(channel="msedge")
        context = browser.new_context(viewport={"width": 1366, "height": 900}, locale="zh-CN", color_scheme="light")
        context.route(
            "https://player.bilibili.com/**",
            lambda route: route.fulfill(
                content_type="text/html; charset=utf-8",
                body="<body style='background:#142019;color:#fff;font:18px system-ui;display:grid;height:100vh;"
                "margin:0;place-items:center'>合成课程播放器</body>",
            ),
        )
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL)
        expect(page.get_by_role("heading", name="自习室")).to_be_visible()
        panel = page.locator("#room-tools")

        # 1. Six built-in cards, desktop 3-column grid, theme images loaded.
        trigger = open_scenes(page, panel)
        assert grid_columns(page, panel) == 3, "desktop scene grid should have 3 columns"
        for theme_id, name in zip(BUILTINS, BUILTIN_NAMES):
            assert card(page, theme_id).count() == 1, theme_id
            assert name in card(page, theme_id).inner_text(), name
        loaded = page.evaluate("""() => Array.from(document.querySelectorAll('#room-tools img'))
            .every(image => image.complete && image.naturalWidth > 0)""")
        assert loaded, "all six built-in covers should decode"
        page.screenshot(path=ROOT / ".dev/theme-panel-six.png", full_page=True)

        # 1b. Limits hint and the persisted background-motion toggle.
        expect(panel.get_by_text(re.compile("ZIP ≤ 32 MiB"))).to_be_visible()
        toggle = panel.get_by_label("背景动效")
        expect(toggle).to_be_checked()
        assert "motion-" in backdrop_class(page), backdrop_class(page)
        toggle.uncheck()
        expect(page.locator(".focus-backdrop")).not_to_have_class(re.compile("motion-"))
        assert saved_motion(page) is False
        page.reload()
        expect(page.get_by_role("heading", name="自习室")).to_be_visible()
        assert "motion-" not in backdrop_class(page), backdrop_class(page)
        assert saved_motion(page) is False
        trigger = open_scenes(page, panel)
        motion = panel.get_by_label("背景动效")
        expect(motion).not_to_be_checked()
        motion.check()
        assert saved_motion(page) is True
        assert "motion-" in backdrop_class(page), backdrop_class(page)

        # 2. Preview only covers the backdrop; applied theme stays until explicit apply.
        card(page, "morning").click()
        expect(panel.get_by_text(re.compile("正在预览：清晨书桌"))).to_be_visible()
        assert "morning" in backdrop_style(page), backdrop_style(page)
        assert saved_scene(page) in (None, "rain")
        page.get_by_role("button", name="应用此场景").click()
        expect(panel).to_be_hidden()
        assert saved_scene(page) == "morning"
        assert "morning" in backdrop_style(page)
        page.reload()
        expect(page.get_by_role("heading", name="自习室")).to_be_visible()
        page.wait_for_function(
            "() => (document.querySelector('.focus-backdrop')?.getAttribute('style') || '').includes('morning')",
            timeout=10000,
        )
        assert "morning" in backdrop_style(page), "applied scene should survive reload"
        assert "清晨书桌" in trigger.get_attribute("aria-label")

        # 3. Keyboard: open focuses first card, Escape restores focus, nothing changes.
        trigger.focus()
        page.keyboard.press("Enter")
        expect(panel).to_be_visible()
        focused = page.evaluate("""() => {
            const active = document.activeElement;
            const card = active && active.closest('[data-theme-id]');
            return card ? card.dataset.themeId : '';
        }""")
        assert focused == "rain", f"first card should receive focus, got {focused!r}"
        page.keyboard.press("Escape")
        expect(panel).to_be_hidden()
        assert page.evaluate("() => (document.activeElement.getAttribute('aria-label') || '').includes('切换场景')")
        assert saved_scene(page) == "morning"

        # 4. Import a synthetic theme pack and apply it.
        archive = make_zip("合成主题包")
        trigger.click()
        expect(panel).to_be_visible()
        panel.locator('input[accept=".zip,application/zip"]').set_input_files(
            {"name": "synthetic-theme.zip", "mimeType": "application/zip", "buffer": archive}
        )
        expect(panel.get_by_text("合成主题包", exact=True)).to_be_visible(timeout=15000)
        custom = panel.locator('[data-kind="custom"]')
        expect(custom).to_have_count(1)
        theme_id = custom.first.get_attribute("data-theme-id")
        assert theme_id and re.fullmatch(r"[a-f0-9]{12}", theme_id), theme_id
        expect(panel.get_by_text(re.compile("正在预览：合成主题包"))).to_be_visible()
        expect(page.locator("video.scene-video")).to_have_count(1)
        page.wait_for_function(
            """() => {
                const video = document.querySelector('video.scene-video');
                return video && !video.paused && video.videoWidth > 0;
            }""",
            timeout=10000,
        )
        page.get_by_role("button", name="应用此场景").click()
        expect(panel).to_be_hidden()
        assert saved_scene(page) == theme_id
        assert f"/api/study/themes/{theme_id}/" in backdrop_style(page), backdrop_style(page)
        page.reload()
        expect(page.get_by_role("heading", name="自习室")).to_be_visible()
        page.wait_for_function(
            "id => (document.querySelector('.focus-backdrop')?.getAttribute('style') || '').includes(id)",
            arg=f"/api/study/themes/{theme_id}/",
            timeout=10000,
        )
        page.wait_for_function(
            """() => {
                const video = document.querySelector('video.scene-video');
                return video && !video.paused && video.videoWidth > 0;
            }""",
            timeout=10000,
        )
        page.screenshot(path=ROOT / ".dev/theme-applied.png", full_page=True)

        # 5. Duplicate upload reuses the existing card; invalid pack reports a reason.
        trigger.click()
        expect(panel).to_be_visible()
        panel.locator('input[accept=".zip,application/zip"]').set_input_files(
            {"name": "synthetic-theme.zip", "mimeType": "application/zip", "buffer": archive}
        )
        expect(panel.get_by_text(re.compile("已在主题库|已存在"))).to_be_visible(timeout=15000)
        expect(panel.locator('[data-kind="custom"]')).to_have_count(1)
        panel.locator('input[accept=".zip,application/zip"]').set_input_files(
            {"name": "broken.zip", "mimeType": "application/zip", "buffer": make_zip("无效主题", background=False)}
        )
        expect(panel.get_by_role("alert")).to_be_visible(timeout=15000)
        expect(panel.locator('[data-kind="custom"]')).to_have_count(1)
        page.screenshot(path=ROOT / ".dev/theme-panel-desktop.png", full_page=True)

        # 5b. Rename the custom theme, export it, and verify motion/video interaction.
        panel.locator('button[aria-label^="重命名主题"]').click()
        rename_input = panel.get_by_label("主题名称")
        expect(rename_input).to_be_visible()
        expect(rename_input).to_be_focused()
        rename_input.fill("动态主题改名")
        rename_input.press("Enter")
        expect(panel.get_by_text("动态主题改名", exact=True)).to_be_visible()
        expect(panel.get_by_text(re.compile("已重命名"))).to_be_visible()
        assert "动态主题改名" in trigger.get_attribute("aria-label")
        export_path = ROOT / ".dev" / "theme-export.zip"
        with page.expect_download() as download_info:
            panel.locator('button[aria-label^="导出主题"]').click()
        download = download_info.value
        assert download.suggested_filename.endswith(".zip"), download.suggested_filename
        download.save_as(export_path)
        with zipfile.ZipFile(export_path) as pack:
            names = set(pack.namelist())
            exported = json.loads(pack.read("theme.json"))
            assert exported["name"] == "动态主题改名", exported
            assert exported["backgroundVideo"] == "assets/loop.webm", exported
            for required in ("assets/background.png", "assets/cover.png", "audio/rain.mp3", "assets/loop.webm"):
                assert required in names, names
            assert ".archive-sha256" not in names
        expect(panel.get_by_text(re.compile("已导出"))).to_be_visible()
        export_path.unlink(missing_ok=True)
        motion = panel.get_by_label("背景动效")
        motion.uncheck()
        expect(page.locator("video.scene-video")).to_have_count(0)
        motion.check()
        expect(page.locator("video.scene-video")).to_have_count(1)
        page.wait_for_function(
            "() => { const video = document.querySelector('video.scene-video'); return video && !video.paused; }",
            timeout=10000,
        )
        page.keyboard.press("Escape")
        expect(panel).to_be_hidden()

        # 6. Narrow screen: single column and no horizontal scroll.
        page.set_viewport_size({"width": 320, "height": 720})
        trigger.click()
        expect(panel).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")
        assert grid_columns(page, panel) == 1, "320px scene grid should have 1 column"
        page.screenshot(path=ROOT / ".dev/theme-panel-mobile.png", full_page=True)
        page.set_viewport_size({"width": 1366, "height": 900})

        # 7. Dark theme keeps the panel usable.
        page.get_by_role("button", name="切换到深色模式").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        expect(panel).to_be_visible()
        page.screenshot(path=ROOT / ".dev/theme-panel-dark.png", full_page=True)
        page.keyboard.press("Escape")
        expect(panel).to_be_hidden()

        # 8. Theme ambient appears in the sound panel and points at the imported asset.
        page.get_by_role("button", name="声音", exact=True).click()
        noise = page.get_by_label("环境音", exact=True)
        expect(noise.locator("option", has_text="主题环境音")).to_have_count(1)
        noise.select_option(label="主题环境音")
        ambient = page.locator('audio[aria-label="主题环境音"]')
        expect(ambient).to_have_count(1)
        source = ambient.get_attribute("src") or ""
        assert f"/api/study/themes/{theme_id}/" in source, source
        page.wait_for_function(
            """() => {
                const audio = document.querySelector('audio[aria-label="主题环境音"]');
                return audio && !audio.paused && audio.duration > 0;
            }""",
            timeout=10000,
        )
        page.keyboard.press("Escape")
        expect(panel).to_be_hidden()

        # 9. Focus timer, course drafts and undo survive theme operations and page round trips.
        duration = page.get_by_role("spinbutton", name="专注时长（分钟）")
        duration.fill("180")
        duration.press("Tab")
        page.get_by_role("button", name="开始专注").click()
        expect(page.get_by_role("button", name="暂停")).to_be_visible()
        page.get_by_role("link", name="看课笔记").click()
        expect(page).to_have_url(URL + "/courses")
        expect(page.get_by_role("heading", name="看课笔记")).to_be_visible()
        lesson = page.get_by_role("textbox", name="B 站视频链接")
        lesson.fill("https://www.bilibili.com/video/BV1abc123XYZ/?p=2&t=60")
        lesson.press("Enter")
        editor = page.get_by_role("textbox", name="课程笔记")
        expect(editor).to_be_visible()
        draft = "主题验收合成笔记"
        editor.fill(draft)
        expect(page.get_by_text("已保存", exact=True)).to_be_visible(timeout=10000)
        editor.press("End")
        editor.press_sequentially(" 追加", delay=20)
        editor.press("Control+z")
        expect(editor).to_have_text(draft)
        page.get_by_role("link", name="返回自习室").click()
        expect(page.get_by_role("heading", name="自习室")).to_be_visible()
        expect(page.get_by_role("button", name="暂停")).to_be_visible()
        assert page.locator('audio[aria-label="主题环境音"]').count() == 1
        page.get_by_role("link", name="看课笔记").click()
        expect(page).to_have_url(URL + "/courses")
        expect(page.get_by_role("textbox", name="课程笔记")).to_have_text(draft)
        page.get_by_role("link", name="返回自习室").click()

        # 10. Delete the applied custom theme and fall back to rain.
        trigger.click()
        expect(panel).to_be_visible()
        custom_card = panel.locator(f'[data-theme-id="{theme_id}"]')
        custom_card.locator('button[aria-label^="删除主题"]').click()
        page.get_by_role("button", name="确认删除").click()
        expect(panel.locator('[data-kind="custom"]')).to_have_count(0)
        assert saved_scene(page) == "rain"
        assert "rain" in backdrop_style(page), backdrop_style(page)
        page.keyboard.press("Escape")

        # 11. The deleted theme is gone after reload as well.
        page.reload()
        expect(page.get_by_role("heading", name="自习室")).to_be_visible()
        trigger.click()
        expect(panel.get_by_role("heading", name="选择场景")).to_be_visible()
        expect(panel.locator('[data-kind="custom"]')).to_have_count(0)
        page.keyboard.press("Escape")

        # 12. Reduced motion turns the animated backdrop off.
        reduced = browser.new_context(viewport={"width": 1366, "height": 900}, locale="zh-CN", reduced_motion="reduce")
        reduced_page = reduced.new_page()
        reduced_page.goto(URL)
        expect(reduced_page.get_by_role("heading", name="自习室")).to_be_visible()
        assert "motion-" not in (reduced_page.locator(".focus-backdrop").get_attribute("class") or "")
        reduced.close()

        assert not errors, errors
        context.close()
        browser.close()
        print("PASS themes: 6 builtins, motion toggle/reduced-motion, preview/apply/reload, keyboard, "
              "ZIP import/duplicate/invalid, video playback, rename/export, limits, 320px, dark mode, "
              "ambient, timer/draft round trip, delete fallback")


def main() -> None:
    site = ROOT / "frontend" / "dist" / "index.html"
    if not site.is_file():
        raise SystemExit("frontend/dist is missing; run npm.cmd --prefix frontend run build first")
    with tempfile.TemporaryDirectory(dir=ROOT / ".dev") as temporary:
        workspace = Path(temporary)
        database = workspace / "state" / "study.db"
        env = os.environ | {"ZHIJING_STUDY_DATABASE": str(database)}
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "zhijing.main:app", "--app-dir", "backend",
             "--host", "127.0.0.1", "--port", "18127"],
            cwd=ROOT,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            wait_service(URL)
            run()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    main()
