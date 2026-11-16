"""Exercise the baseline Vue editor through the pilot Vite proxy and real note APIs."""

import argparse
import os
from time import monotonic, sleep
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright

from verify_contract import MOCK, NOTE


def wait_for_call(text, state):
    deadline = monotonic() + 10
    while monotonic() < deadline:
        calls = httpx.get(MOCK + "/calls").json()
        if any(call["text"] == text and call["state"] == state for call in calls):
            return
        sleep(0.1)
    raise AssertionError(f"Mock did not report {state} for the synthetic note")


def run(page, base):
    created = []
    run_id = uuid4().hex[:8]

    def api(path, method="GET", payload=None):
        options = {"data": payload} if payload is not None else {}
        response = page.request.fetch(base + path, method=method, **options)
        assert response.ok, response.text()
        result = response.json()
        assert result["code"] == 200, result
        return result["data"]

    def note(label, text):
        title = f"知径合成验收 {run_id} {label}"
        created_note = api("/api/notes", "POST", {"title": title, "content": text, "tagIds": []})
        created.append(created_note["id"])
        return created_note["id"], title

    def editor():
        return page.get_by_role("tabpanel")

    def open_note(note_id, title, first=False):
        path = f"/notes/{note_id}"
        if first:
            page.goto(base + path)
        else:
            # Use the application's router so both real note editors stay mounted.
            page.evaluate("(path) => document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(path).then(() => null)", path)
        expect(editor().get_by_label("笔记标题")).to_have_value(title)
        expect(editor().get_by_role("button", name="润色", exact=True)).to_be_enabled()

    def content(note_id):
        return api(f"/api/notes/{note_id}")["content"]

    dialog = page.locator(".el-dialog:visible")

    try:
        actions = [("润色", "合成润色句"), ("整理格式", "**合成排版句**")]
        for index, (action, replacement) in enumerate(actions):
            note_id, title = note(action, NOTE)
            open_note(note_id, title, first=index == 0)
            editor().get_by_role("button", name=action, exact=True).click()
            expect(dialog.locator(".ai-progress-phase")).to_contain_text("正在处理")
            expect(dialog.locator(".el-dialog__title")).to_contain_text("结果预览", timeout=12000)
            expect(dialog.locator(".ai-preview")).to_contain_text(replacement.strip("*"))
            assert content(note_id) == NOTE
            dialog.get_by_role("button", name="替换正文").click()
            expect(dialog).to_have_count(0)
            assert content(note_id) == NOTE
            with page.expect_response(lambda response: f"/api/notes/{note_id}" in response.url
                                      and response.request.method == "PUT"):
                editor().get_by_role("button", name="保存", exact=True).click()
            assert content(note_id) == NOTE.replace("合成原句", replacement)
            print(f"PASS Python {action}: progress, preview, apply, explicit save", flush=True)

        cancel_text = f"{NOTE} {run_id} 合成慢请求"
        cancel_id, cancel_title = note("取消", cancel_text)
        open_note(cancel_id, cancel_title)
        editor().get_by_role("button", name="润色", exact=True).click()
        expect(dialog.locator(".ai-progress-phase")).to_contain_text("正在处理")
        wait_for_call(cancel_text, "pending")
        dialog.get_by_role("button", name="取消处理").click()
        expect(dialog).to_have_count(0)
        wait_for_call(cancel_text, "cancelled")
        assert content(cancel_id) == cancel_text
        print("PASS cancellation: upstream disconnected and stored note unchanged", flush=True)

        b_text = "## 独立笔记\n\n这是第二份合成笔记。"
        b_draft = b_text + "\n\n第二份笔记仍有未保存的正文草稿。"
        b_id, b_title = note("草稿 B", b_text)
        open_note(b_id, b_title)
        editor().get_by_role("button", name="源码对照").click()
        source = editor().locator(".cm-content")
        source.fill(b_draft)
        expect(editor().locator(".save-state")).to_contain_text("未保存")
        assert content(b_id) == b_text

        a_text = f"{NOTE} {run_id} 切换验收 合成慢请求"
        a_id, a_title = note("润色 A", a_text)
        open_note(a_id, a_title)
        editor().get_by_role("button", name="润色", exact=True).click()
        expect(dialog.locator(".ai-progress-phase")).to_contain_text("正在处理")
        wait_for_call(a_text, "pending")
        page.go_back()
        expect(editor().get_by_label("笔记标题")).to_have_value(b_title)
        expect(source).to_contain_text("第二份笔记仍有未保存的正文草稿")
        # The baseline dialog is appended to the body. An inactive editor must reject apply.
        expect(dialog.locator(".el-dialog__title")).to_contain_text("结果预览", timeout=12000)
        dialog.get_by_role("button", name="替换正文").click()
        expect(page.get_by_text("当前笔记已切换，请回到目标笔记重试", exact=True)).to_be_visible()
        dialog.get_by_role("button", name="取消", exact=True).click()
        expect(dialog).to_have_count(0)
        expect(source).to_contain_text("第二份笔记仍有未保存的正文草稿")
        assert content(a_id) == a_text and content(b_id) == b_text
        print("PASS switch while processing: stale apply rejected, B draft preserved, both saved bodies unchanged", flush=True)
    finally:
        for note_id in reversed(created):
            api(f"/api/notes/{note_id}", "DELETE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy", default="http://127.0.0.1:15174")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.getenv("ZHIJING_CHROMIUM_PATH"))
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        run(page, args.proxy)
