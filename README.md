# 知径

知径是一个独立的个人学习工作台。当前包含本地自习室和 Markdown 流式润色接口。

## 项目结构

| 位置 | 内容 |
| --- | --- |
| `frontend/` | Vue、TypeScript 和 Vite 自习室界面。CodeMirror 管理各节课的 Markdown 草稿和撤销记录。 |
| `backend/zhijing/` | FastAPI 入口、自习室 SQLite 存储、Markdown 导出和流式润色。 |
| `tests/` | 自习室存储、导出和润色接口的回归测试。 |
| `dev/`、`docs/` | 模拟模型，以及 LearnHub 兼容试点的复验脚本和记录。 |

## 自习室 MVP

1. 粘贴 B 站视频链接进入课程。常规视频支持分 P，课堂和番剧链接通过 B 站原页观看，也可以在知径记笔记。
2. 边看边写 Markdown。输入时间点可插到光标处，可从笔记下方的时间点跳回视频，也可将其设为续播点。自习室重开时恢复最近课程、续播点和已保存的笔记。B 站外链没有公开读取当前进度的接口，续播点由用户设置。
3. 笔记自动保存至本机 SQLite，支持下载 Markdown。要直接保存到 Obsidian，设置目标目录后点击「保存到 Obsidian」。如果同名文件的内容已被外部改动，知径会保留原文件。
4. 在雨窗和夜间图书馆之间切换，选择白噪音、粉噪音、棕噪音或导入本地音频。歌单保存在当前浏览器中。

<details>
<summary>场景图和生成提示词</summary>

两幅场景图由内置 imagegen 生成，分别保存为 `frontend/src/assets/rain.jpg` 和 `frontend/src/assets/library.jpg`。

`rain.jpg`

> Use case: photorealistic-natural. Asset: wide panoramic banner in a personal study room app, displayed as a horizontal crop. Create a quiet study desk at a large rain-streaked window looking out over foggy evergreen forest and distant hills, walnut wood, open blank notebook, small warm amber table lamp on the right, tactile details. Landscape, wide composition; the left third is low-contrast dark olive shadow and window with room for white overlay controls, visual focus sits on the center-right. Cinematic editorial interior photography, soft diffused rainy daylight, forest green, warm amber. No people, no writing, no text, no branding, no watermark.

`library.jpg`

> Use case: photorealistic-natural. Asset: wide panoramic banner in a personal study room app, displayed as a horizontal crop. Create the quiet corner of a private library in the evening, tall wooden bookshelves in soft shadow, a walnut writing desk, vintage green-shaded desk lamp near the right, warm amber pool of light, slight rain-blue evening light through a narrow window. Landscape, wide composition, low-contrast dark left third for white overlay controls, illuminated point of interest center-right. Cinematic editorial interior photography with rich natural texture and subdued espresso and green tones. No people, no legible writing, no text, no branding, no watermark.

</details>

## Docker 启动

在仓库根目录执行以下命令。首次构建会拉取 Node 和 Python 基础镜像，构建前端并安装锁定的 Python 依赖。

```powershell
docker compose up -d --build --wait
```

打开 [Docker 自习室](http://127.0.0.1:18119/)。可用 `ZHIJING_DOCKER_PORT` 调整宿主机端口。Docker 自习室使用独立的 `study-data` 卷保存 SQLite，浏览器歌单随访问地址保存。运行 `docker compose down` 可停止容器并保留卷。

需要直接写入 Obsidian 时，在仓库根目录创建 `compose.override.yaml`，把示例路径改成已存在的 Vault 子目录，再运行启动命令。

```yaml
services:
  zhijing:
    environment:
      ZHIJING_STUDY_OBSIDIAN_DIR: /obsidian
    volumes:
      - type: bind
        source: D:/ExampleVault/ZhiJing
        target: /obsidian
        bind:
          create_host_path: false
```

## 本地启动

需要 Python 3.11 或更新版本、uv 与 Node.js 22.12 或更新版本。在知径根目录执行以下 PowerShell 命令。

```powershell
uv sync --locked --default-index https://pypi.org/simple
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
uv run --locked --no-sync uvicorn zhijing.main:app --app-dir backend --host 127.0.0.1 --port 18081
```

打开 [本地自习室](http://127.0.0.1:18081/)。默认 SQLite 路径为 `.data/study.sqlite3`。需要写入 Obsidian 时，在 `.env` 用 `ZHIJING_STUDY_OBSIDIAN_DIR` 指定一个已存在的 Vault 子目录，保存配置后重启服务。Windows 路径可以使用正斜杠。

前端开发时，可让上述 FastAPI 服务继续运行，在另一个终端执行 `npm.cmd --prefix frontend run dev`，通过 Vite 的本地地址访问界面。

## 流式润色

接口开发可以单独运行 FastAPI。使用示例配置时，在另一个终端启动模拟模型。

```powershell
uv run --locked --no-sync uvicorn dev.mock_model:app --host 127.0.0.1 --port 18082
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

Python 测试使用临时 SQLite 文件，无需启动外部数据库。前期与 LearnHub 旧编辑器的兼容验证见 [试点记录](docs/learnhub-pilot.md)。

项目约定和两份 Markdown 技能源自 LearnHub `767b4aa`，相关材料适用 [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)。

Required Notice: Copyright (c) 2026 QiuLf
