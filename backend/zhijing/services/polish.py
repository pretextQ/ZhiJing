import asyncio
import json
import logging
from pathlib import Path
from time import monotonic

import httpx

from ..settings import Settings
from .markdown import (
    JAVA_TRIM,
    JAVA_WHITESPACE,
    char_count,
    complete_fragment,
    split_for_polish,
)

SKILLS = Path(__file__).resolve().parents[1] / "skills"
POLISH_MATH = """【数学与代码保留规则】
本次仅润色文字，已有 LaTeX 公式、公式分隔符、真实代码、命令、SQL、配置和日志逐字保留；不将数学公式改成代码或伪代码，不转换原代码，不补造或新增公式。"""
FORMAT_MATH = r"""【数学表达与代码的选择】
能准确用数学公式表达的知识，一律优先用 LaTeX 公式：变量与上下标、概率分布、相似度与评分、损失函数、状态/参数更新、复杂度、定义、约束和推导。
行内公式使用 $…$；独立公式的起止 $$ 各自独占一行。多行推导在同一数学块中使用 aligned 或 cases，保留上下标、分式、矩阵和括号结构。
Markdown 正文中的 LaTeX 命令使用单个反斜杠，不额外做 Markdown 转义；工具参数是 JSON 时仅按 JSON 规则转义一次，解析后的正文仍应是正常 LaTeX。
数学表达不要放在行内反引号、缩进代码块或任何围栏代码块（包括 text、latex、python）里；也不要用伪代码、ASCII/Unicode 拼接、图片或程序函数代替本可直接排版的公式。
例如双编码器评分写成 $s(q,d)=\langle E_q(q),E_d(d)\rangle$，不要写成代码 dot(E_q(q), E_d(d))；公式后用正文说明变量含义与适用条件。
只有真实程序实现、命令、SQL、配置、日志，或用户明确要求演示源码时，才使用代码格式；真实代码保持原有语言与内容，不强行改成公式。
沿用来源和原文中的定义、数值与条件，不补造缺乏依据的公式。输出前检查：数学表达已在公式分隔符内，代码块仅承载真实代码，LaTeX 分隔符和环境成对闭合。
本次只整理现有内容的格式，不新增知识。只将语义明确的数学表达改为公式，保持原数值、符号含义和条件；无法确定的表达保留原文，不猜测公式。已有正确 LaTeX 和真实代码逐字保留。"""
TIMEOUT = (
    "AI 请求超时（本轮剩余时间不足）。"
    "可以在设置里把「思考模式」切为「关闭」，或分段选中后再处理。"
)
INCOMPLETE = "AI分段输出未完整结束，本次改动未应用，原文保留；可缩短单段要求后重试"
log = logging.getLogger(__name__)


class PolishError(Exception):
    pass


def load_prompt(is_format: bool) -> tuple[str, float]:
    skill = "markdown-beautify" if is_format else "markdown-polish"
    try:
        source = (SKILLS / f"{skill}.md").read_text(encoding="utf-8")
        header, delimiter, body = source.removeprefix("---\n").partition("\n---\n")
        if not delimiter or not body.strip():
            raise PolishError(f"技能文件正文为空或格式无效：{skill}")
    except (OSError, UnicodeError) as error:
        raise PolishError(f"技能文件读取失败：{skill}") from error

    ratio = 0.6
    for line in header.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "min_ratio":
            try:
                configured = float(value)
                if 0 < configured <= 1:
                    ratio = configured
            except ValueError:
                pass
            break
    math_prompt = FORMAT_MATH if is_format else POLISH_MATH
    return f"{body.strip()}\n\n{math_prompt}", ratio


async def request_completion(
    client: httpx.AsyncClient, settings: Settings, prompt: str, text: str, budget: float
) -> str:
    url = str(settings.base_url).rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.model.strip(),
        "max_tokens": settings.max_tokens,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
    }
    if not settings.model.lower().startswith(("kimi-k3", "glm-5.3")):
        payload["temperature"] = settings.temperature
    if settings.base_url.host == "api.deepseek.com":
        payload["thinking"] = {"type": "disabled"}
    try:
        async with asyncio.timeout(budget):
            response = await client.post(
                url,
                headers={"Authorization": "Bearer " + settings.api_key.get_secret_value().strip()},
                json=payload,
                timeout=budget,
            )
    except (TimeoutError, httpx.TimeoutException) as error:
        raise PolishError(TIMEOUT) from error
    except httpx.HTTPError as error:
        raise PolishError("AI 服务异常: 无法读取模型响应") from error

    if response.status_code != 200:
        raise PolishError(f"AI 服务异常: AI 服务调用失败({response.status_code})")
    try:
        choice = response.json()["choices"][0]
        message = choice["message"]
        if not isinstance(message, dict):
            raise TypeError("Expected a message object")
    except (KeyError, IndexError, ValueError, TypeError) as error:
        raise PolishError("AI 服务异常: AI 服务返回格式异常") from error
    if choice.get("finish_reason") != "stop":
        raise PolishError(INCOMPLETE)
    content = message.get("content")
    if not isinstance(content, str) or not content.strip(JAVA_WHITESPACE):
        raise PolishError("AI 未返回有效内容，请稍后重试")
    return content


def frame(event: str, data: dict) -> bytes:
    # The Vue parser uses literal LF pairs. Keep all Markdown line breaks inside JSON.
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event:{event}\ndata:{encoded}\n\n".encode("utf-8", errors="backslashreplace")


async def polish_events(client: httpx.AsyncClient, settings: Settings, text: str, mode: str | None):
    try:
        if not (settings.base_url and settings.model.strip() and settings.api_key.get_secret_value().strip()):
            raise PolishError(
                "智能体尚未配置 API Key：请设置 ZHIJING_AI_BASE_URL、ZHIJING_AI_MODEL 和 ZHIJING_AI_API_KEY"
            )
        is_format = (mode or "").lower() == "format"
        prompt, ratio = load_prompt(is_format)
        chunks = split_for_polish(text)
        total = len(chunks)
        yield frame("progress", {"stage": "start", "total": total})
        deadline = monotonic() + settings.round_timeout
        output = []
        for index, part in enumerate(chunks, 1):
            if not part.strip(JAVA_TRIM).strip(JAVA_WHITESPACE):
                output.append(part)
                continue
            yield frame("progress", {"stage": "chunk", "index": index, "total": total})
            remaining = deadline - monotonic()
            if remaining < settings.min_chunk_time:
                action = "整理格式" if is_format else "润色"
                raise PolishError(
                    f"全文过长（共 {total} 段），{action} 已用满 {settings.round_timeout:g} 秒预算"
                    f"（完成 {index - 1} 段）。请分段选中后再处理，或在设置里把「思考模式」切为「关闭」后重试。"
                )
            user_text = part
            if total > 1:
                user_text = (
                    f"【这是全文的第 {index}/{total} 段，请只处理本段，保持与原文相同的详略程度，不要写任何说明文字】\n\n"
                    + part
                )
            content = await request_completion(client, settings, prompt, user_text, remaining)
            if not complete_fragment(content):
                raise PolishError(
                    f"第{index}/{total}段公式或代码围栏未完整闭合，本次整理未应用，原文保留，请重试"
                )
            output.append(content.strip(JAVA_TRIM))
        result = "\n\n".join(output).strip(JAVA_TRIM)
        if char_count(result) < char_count(text) * ratio:
            result = text
        yield frame("done", {"content": result})
    except PolishError as error:
        yield frame("failed", {"message": str(error)})
    except Exception:
        log.exception("润色服务异常")
        yield frame("failed", {"message": "AI 服务异常"})
