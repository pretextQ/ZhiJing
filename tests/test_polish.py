import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from zhijing.settings import Settings, StudySettings
from zhijing.main import create_app
from zhijing.services.markdown import complete_fragment, split_for_polish
from zhijing.services.polish import INCOMPLETE, TIMEOUT

ENDPOINT = "/api/ai/polish-stream"
NOTE = "## 合成笔记\n\n这里是一段供接口验收使用的合成原句。"
FORMULA = "$$\n" + r"\begin{aligned}a &= b + c \\" + "\n\n" + r"d &= e\end{aligned}" + "\n$$"
CODE = "````markdown\n```python\nprint(42)\n```\n\n````"
TABLE = "| 项目 | 值 |\n| --- | --- |\n| 合成 | 42 |"


def events(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert b"\r" not in response.content
    frames = response.text.split("\n\n")
    assert frames.pop() == ""
    return [
        (event.removeprefix("event:"), json.loads(data.removeprefix("data:")))
        for event, data in (item.split("\n") for item in frames)
    ]


@pytest.fixture
def open_api(monkeypatch, tmp_path):
    original = httpx.AsyncClient

    def create(handler, **overrides):
        transport = httpx.MockTransport(handler)
        monkeypatch.setattr(httpx, "AsyncClient", lambda: original(transport=transport))
        return TestClient(
            create_app(
                Settings(
                    _env_file=None,
                    **{
                        "base_url": "http://model.example/v1/",
                        "model": "synthetic-note",
                        "api_key": "synthetic-key",
                        "round_timeout": 1,
                        "min_chunk_time": 0,
                        **overrides,
                    },
                ),
                StudySettings(_env_file=None, database=tmp_path / "state" / "study.db"),
            )
        )

    return create


def model_response(content, finish="stop"):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}]})


@pytest.mark.parametrize("payload", [{}, {"text": None}, {"text": ""}, {"text": " \t\n"}])
def test_blank_returns_spring_business_error(open_api, payload):
    def unexpected_call(_request):
        pytest.fail("invalid requests must never call the model")

    with open_api(unexpected_call) as api:
        response = api.post(ENDPOINT, json=payload)
    assert response.status_code == 200
    assert response.json() == {"code": 400, "msg": "内容不能为空", "data": None}


@pytest.mark.parametrize("payload", [{"text": {}}, {"text": NOTE, "mode": []}, [NOTE]])
def test_wrong_json_shape_fails_before_stream(open_api, payload):
    with open_api(lambda _: pytest.fail("unexpected completion")) as api:
        response = api.post(ENDPOINT, json=payload)
    assert response.status_code == 500
    assert response.json()["code"] == 500
    assert response.json()["msg"].startswith("服务器内部错误: JSON parse error:")
    assert response.json()["data"] is None


@pytest.mark.parametrize("mode", ["format", "FoRmAt", "polish", "unknown", "", None])
def test_modes_and_event_order(open_api, mode):
    def model(request):
        assert str(request.url) == "http://model.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer synthetic-key"
        body = json.loads(request.content)
        assert body["model"] == "synthetic-note"
        assert body["max_tokens"] == 8192
        assert body["messages"][1] == {"role": "user", "content": NOTE}
        prompt = body["messages"][0]["content"]
        assert ("技术笔记排版助手" in prompt) == ((mode or "").lower() == "format")
        assert "LaTeX" in prompt
        return model_response(NOTE.replace("原句", "新句"))

    with open_api(model) as api:
        assert events(api.post(ENDPOINT, json={"text": NOTE, "mode": mode, "extra": 42})) == [
            ("progress", {"stage": "start", "total": 1}),
            ("progress", {"stage": "chunk", "index": 1, "total": 1}),
            ("done", {"content": NOTE.replace("原句", "新句")}),
        ]


@pytest.mark.parametrize(
    "result,finish,event,expected",
    [
        (NOTE, "length", "failed", {"message": INCOMPLETE}),
        (NOTE, None, "failed", {"message": INCOMPLETE}),
        ("", "stop", "failed", {"message": "AI 未返回有效内容，请稍后重试"}),
        ("短句", "stop", "done", {"content": NOTE}),
        (NOTE + "\n\n```python\nprint(42)", "stop", "failed",
         {"message": "第1/1段公式或代码围栏未完整闭合，本次整理未应用，原文保留，请重试"}),
    ],
)
def test_output_guards(open_api, result, finish, event, expected):
    with open_api(lambda _: model_response(result, finish)) as api:
        response = events(api.post(ENDPOINT, json={"text": NOTE}))
    assert response[-1] == (event, expected)


def test_timeout_and_no_partial_candidate(open_api):
    async def slow_model(_request):
        await asyncio.sleep(1)
        return model_response(NOTE)

    with open_api(slow_model, round_timeout=0.05) as api:
        response = events(api.post(ENDPOINT, json={"text": NOTE}))
    assert [event for event, _ in response] == ["progress", "progress", "failed"]
    assert response[-1][1] == {"message": TIMEOUT}


def test_last_chunk_failure_discards_earlier_candidate(open_api):
    text = "甲" * 3500 + "\n\n" + "乙" * 3500
    replies = iter([model_response("丙" * 3500), model_response("丁" * 3500, "length")])
    with open_api(lambda _: next(replies)) as api:
        response = events(api.post(ENDPOINT, json={"text": text}))
    assert response == [
        ("progress", {"stage": "start", "total": 2}),
        ("progress", {"stage": "chunk", "index": 1, "total": 2}),
        ("progress", {"stage": "chunk", "index": 2, "total": 2}),
        ("failed", {"message": INCOMPLETE}),
    ]


def test_unconfigured_fails_before_progress(open_api):
    with open_api(lambda _: pytest.fail("unexpected completion"), api_key="") as api:
        response = events(api.post(ENDPOINT, json={"text": NOTE}))
    assert len(response) == 1 and response[0][0] == "failed"
    assert "ZHIJING_AI_API_KEY" in response[0][1]["message"]


def test_long_note_assembled_in_original_order(open_api):
    text = "\n\n".join([NOTE * 130, FORMULA, TABLE, CODE, NOTE * 130])
    received = []

    def model(request):
        body = json.loads(request.content)
        part = body["messages"][1]["content"].split("\n\n", 1)[1]
        assert complete_fragment(part)
        received.append(part)
        return model_response(part)

    with open_api(model) as api:
        response = events(api.post(ENDPOINT, json={"text": text}))
    assert len(received) > 1
    assert response[0] == ("progress", {"stage": "start", "total": len(received)})
    assert response[-1] == ("done", {"content": text})
    for excerpt in (FORMULA, TABLE, CODE):
        assert sum(excerpt in part for part in received) == 1


def test_oversized_code_table_and_math_keep_valid_parts():
    code = "````python\n" + "\n".join(f"item_{i} = 42" for i in range(900)) + "\n````"
    table_head = "| 项目 | 值 |\n| --- | --- |\n"
    table = table_head + "\n".join(f"| 合成数据 {i} | 42 |" for i in range(500))
    math = "\\[\n" + "\n".join(rf"x_{{{i}}} = x_{{{i+1}}} \\" for i in range(300)) + "\n\\]"
    code_parts = split_for_polish(code)
    table_parts = split_for_polish(table)
    assert len(code_parts) > 1
    assert len(table_parts) > 1
    assert all(part.startswith("````python\n") and complete_fragment(part) for part in code_parts)
    assert all(part.startswith(table_head) for part in table_parts)
    assert "\n".join(part.split("\n", 1)[1].rsplit("\n", 1)[0] for part in code_parts) == code.split("\n", 1)[1].rsplit("\n", 1)[0]
    assert "\n".join(part.removeprefix(table_head) for part in table_parts) == table.removeprefix(table_head)
    assert split_for_polish(math) == [math]
