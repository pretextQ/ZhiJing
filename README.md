# 知径

知径是一个独立的个人学习工作台，后端使用 Python 和 FastAPI。目前可运行的功能是 Markdown 流式润色与整理格式。知径自己的笔记存储和工作台界面待开发。

## 本地启动

需要 Python 3.11 或更新版本与 uv。在知径根目录执行以下 PowerShell 命令。

```powershell
uv sync --locked --default-index https://pypi.org/simple
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

示例配置使用模拟模型。分别在两个终端启动模拟模型和 FastAPI。

```powershell
uv run --locked --no-sync uvicorn dev.mock_model:app --host 127.0.0.1 --port 18082
```

```powershell
uv run --locked --no-sync uvicorn zhijing.main:app --app-dir backend --host 127.0.0.1 --port 18081
```

打开 [FastAPI 接口文档](http://127.0.0.1:18081/docs)，或在 PowerShell 中直接读取 SSE。

```powershell
@{ text = '这是一段用于验收的合成原句。'; mode = 'polish' } |
  ConvertTo-Json -Compress |
  curl.exe --no-buffer -H 'Content-Type: application/json' --data-binary '@-' http://127.0.0.1:18081/api/ai/polish-stream
```

接口接受 `polish`（润色）和 `format`（整理格式）。处理中发送 `progress`，完成后通过 `done` 返回候选正文，失败时发送 `failed`。

接入模型服务时，在 `.env` 或进程环境中设置 `ZHIJING_AI_BASE_URL`、`ZHIJING_AI_MODEL` 和 `ZHIJING_AI_API_KEY`。基址填 OpenAI 兼容 API 的基址，例如 `http://127.0.0.1:18082/v1`，服务会追加 `/chat/completions`。默认处理预算是 270 秒，默认最大输出为 8192 tokens。

## 测试

```powershell
uv run --locked --no-sync pytest -q
```

现有 Python 接口和测试可在没有 Java 服务或数据库的环境中运行。前期与 LearnHub 旧编辑器的兼容验证见 [试点记录](docs/learnhub-pilot.md)。

项目约定和两份 Markdown 技能源自 LearnHub `767b4aa`，相关材料适用 [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)。

Required Notice: Copyright (c) 2026 QiuLf
