"""Synthetic OpenAI-compatible model for the migration pilot."""

import asyncio
import re
from time import monotonic

from fastapi import FastAPI, Request

app = FastAPI()
calls = []
CHUNK_HEADER = re.compile(r"^【这是全文的第 .*?】\n\n")


@app.get("/calls")
def recorded_calls():
    return calls


@app.post("/v1/chat/completions")
async def complete(request: Request):
    payload = await request.json()
    prompt, text = [message["content"] for message in payload["messages"]]
    text = CHUNK_HEADER.sub("", text, count=1)
    format_mode = "技术笔记排版助手" in prompt
    call = {
        "model": payload["model"],
        "mode": "format" if format_mode else "polish",
        "text": text,
        "state": "pending",
    }
    calls.append(call)

    end = monotonic() + (8 if "合成慢请求" in text else 0.4)
    while monotonic() < end:
        if await request.is_disconnected():
            call["state"] = "cancelled"
            return {"choices": []}
        await asyncio.sleep(0.05)
    call["state"] = "complete"

    result = text.replace("合成原句", "**合成排版句**" if format_mode else "合成润色句")
    finish = "length" if "合成截断" in text else "stop"
    if "合成缩水" in text:
        result = "短。"
    if "合成围栏缺失" in text:
        result += "\n\n```python\nprint(42)"
    return {"choices": [{"finish_reason": finish, "message": {"content": result}}]}
