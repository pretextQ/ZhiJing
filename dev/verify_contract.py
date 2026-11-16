"""Compare both real development backends using the synthetic model."""

import argparse
import json
from time import monotonic

import httpx

PATH = "/api/ai/polish-stream"
SPRING = "http://127.0.0.1:18080"
PYTHON = "http://127.0.0.1:18081"
MOCK = "http://127.0.0.1:18082"
PROXY = "http://127.0.0.1:15174"
SHORT_BUDGET_BACKEND = "http://127.0.0.1:18083"
NOTE = "## 合成笔记\n\n这是用来验收流式润色和整理格式的一段合成原句。"
TABLE = "| 样本 | 数值 |\n| --- | --- |\n| A | 42 |"
CODE = "````markdown\n```python\nprint(42)\n```\n\n````"
MATH = "$$\n" + r"\begin{aligned}a &= b + c \\" + "\n\n" + r"d &= e\end{aligned}" + "\n$$"
LONG_NOTE = "\n\n".join([NOTE.split("\n\n")[1] * 135, MATH, TABLE, CODE, NOTE.split("\n\n")[1] * 135])


def parse_frame(frame):
    event, data = frame.split(b"\n")
    return event.removeprefix(b"event:").decode(), json.loads(data.removeprefix(b"data:"))


def post(client, base, payload):
    response = client.post(base + PATH, json=payload)
    media = response.headers["content-type"].split(";")[0]
    if media == "text/event-stream":
        raw = response.content
        assert b"\r" not in raw and raw.endswith(b"\n\n"), repr(raw[:150])
        result = [parse_frame(frame) for frame in raw[:-2].split(b"\n\n")]
    else:
        result = response.json()
    return response.status_code, media, result


def compare(client):
    cases = {
        "default": {"text": NOTE},
        "format": {"text": NOTE, "mode": "format"},
        "case-insensitive format": {"text": NOTE, "mode": "FoRmAt"},
        "unknown mode": {"text": NOTE, "mode": "other"},
        "null mode": {"text": NOTE, "mode": None},
        "missing body": None,
        "missing text": {},
        "null text": {"text": None},
        "blank text": {"text": " \t\n"},
        "Unicode whitespace": {"text": "\u3000"},
        "wrong field type": {"text": {}},
        "wrong top-level shape": [],
        "truncated completion": {"text": NOTE + "合成截断"},
        "invalid Markdown": {"text": NOTE + "合成围栏缺失"},
        "output too short": {"text": NOTE + "合成缩水"},
        "long Markdown": {"text": LONG_NOTE},
    }
    for name, payload in cases.items():
        java = post(client, SPRING, payload)
        python = post(client, PYTHON, payload)
        assert java == python, (name, java, python)
        if name == "long Markdown":
            frames = python[2]
            assert frames[0][1]["total"] > 1
            assert frames[-1] == ("done", {"content": LONG_NOTE.replace("合成原句", "合成润色句")})
        print(f"PASS {name}: {python[0]} {python[1]}", flush=True)
    bodies = []
    for base in (SPRING, PYTHON):
        bad = client.post(base + PATH, content=b"{", headers={"Content-Type": "application/json"})
        assert bad.status_code == 500
        assert bad.json().keys() == {"code", "msg", "data"}
        assert bad.json()["code"] == 500 and bad.json()["data"] is None
        assert bad.json()["msg"].startswith("服务器内部错误: JSON parse error:")
        bodies.append(bad.json())
    print(f"PASS malformed JSON structure; identical diagnostic={bodies[0] == bodies[1]}")


def proxy_test(client, base, mode):
    call_count = len(client.get(MOCK + "/calls").json())
    # A slow upstream makes buffering observable while keeping this check independent of rendering.
    slow_note = NOTE + " 路由验收 合成慢请求"
    before = monotonic()
    with client.stream("POST", base + PATH, json={"text": slow_note}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        frames = []
        buf = b""
        first_progress = None
        for data in response.iter_raw():
            assert b"\r" not in data
            buf += data
            while b"\n\n" in buf:
                frame, buf = buf.split(b"\n\n", 1)
                frames.append(parse_frame(frame))
                if first_progress is None:
                    first_progress = monotonic() - before
        assert not buf
    elapsed = monotonic() - before
    assert [event for event, _ in frames] == ["progress", "progress", "done"]
    assert frames[-1][1] == {"content": slow_note.replace("合成原句", "合成润色句")}
    assert first_progress is not None
    if mode == "python":
        assert elapsed - first_progress > 5, (first_progress, elapsed)
        assert response.headers["x-accel-buffering"] == "no"
    calls = client.get(MOCK + "/calls").json()[call_count:]
    assert [(call["model"], call["state"]) for call in calls if call["text"] == slow_note] == [
        (f"synthetic-{mode}", "complete")
    ]
    assert client.get(base + "/api/ai/status").json()["data"]["model"] == "synthetic-spring"
    print(f"PASS {mode} Vite route: first progress {first_progress:.3f}s, done {elapsed:.3f}s")


def timeout_test(client):
    status, media, frames = post(client, SHORT_BUDGET_BACKEND, {"text": NOTE + " 合成慢请求"})
    assert (status, media) == (200, "text/event-stream")
    assert frames[:2] == [
        ("progress", {"stage": "start", "total": 1}),
        ("progress", {"stage": "chunk", "index": 1, "total": 1}),
    ]
    assert len(frames) == 3 and frames[2][0] == "failed"
    assert frames[2][1]["message"].startswith("AI 请求超时")
    print("PASS live Python timeout; only failed terminal event")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["compare", "python", "spring", "timeout"])
    parser.add_argument("--proxy", default=PROXY)
    args = parser.parse_args()
    with httpx.Client(timeout=20, trust_env=False) as client:
        if args.mode == "compare":
            compare(client)
        elif args.mode == "timeout":
            timeout_test(client)
        else:
            proxy_test(client, args.proxy, args.mode)
