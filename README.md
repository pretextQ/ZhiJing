# 知径

知径是一个独立的个人学习工作台。当前包含本地自习室和 Markdown 流式润色接口。

> 项目基调见 [项目基调](docs/project-charter.md)。知径是单人自用的线上自习室：不做账号、社交、联机、多租户与商业化，后续开发以此为准。

## 项目结构

| 位置 | 内容 |
| --- | --- |
| `frontend/` | Vue、TypeScript 和 Vite 自习室界面。CodeMirror 管理各节课的 Markdown 草稿和撤销记录。 |
| `backend/zhijing/` | 模块化单体：`api/` 路由、`services/` 业务、`infra/` 数据库与文件、`domain/` 模型、`legacy/` 润色兼容层。 |
| `frontend/src/` | Vue 3 + vue-router + Pinia；`views/`、`stores/`、`components/`、`styles/` 与生成的 `api/schema.d.ts`。 |
| `tests/` | 数据库迁移、备份、自习室存储、主题包、导出和润色接口的回归测试。 |
| `dev/`、`docs/` | 模拟模型、素材生成、备份/恢复/OpenAPI/验收脚本，以及项目基调、主题包说明和历次实施记录。 |
| `.github/workflows/ci.yml` | 后端 ruff + pytest、前端 lint/格式/单测/构建与 OpenAPI 类型一致性检查。 |

## 自习室 MVP

1. 打开自习室即可开始专注。首页提供专注和休息计时、本轮目标、学习待办及今日专注统计。右侧独立调节本地音乐和环境音。顶栏可切换六款内置场景、导入 ZIP 主题包或开启沉浸模式，沉浸模式保留小计时器和场景、声音入口。计时、目标、待办、统计和歌单保存在当前浏览器中。
2. 从右上角进入「看课笔记」，粘贴 B 站链接打开课程。常规视频支持分 P，课堂和番剧链接通过 B 站原页观看，也可以在知径记笔记。返回自习室后，专注计时和背景音继续运行。
3. 边看边写 Markdown。输入时间点可插到光标处，可从笔记下方的时间点跳回视频，也可将其设为续播点。再次打开「看课笔记」时恢复最近课程、续播点和已保存的笔记。B 站外链没有公开读取当前进度的接口，续播点由用户设置。
4. 笔记自动保存至本机 SQLite，支持下载 Markdown。要直接保存到 Obsidian，设置目标目录后点击「保存到 Obsidian」。如果同名文件的内容已被外部改动，知径会保留原文件。

## 场景与主题包

点击首页顶栏的当前场景打开面板。面板包含雨窗、夜间图书馆、清晨书桌、海边木屋、暮色列车和像素夏夜六款主题。内置场景带轻微的背景动效，可在面板中用「背景动效」开关关闭；系统开启减少动效时自动停用。点击卡片先预览，点「应用此场景」保存并关闭面板；按 Escape 放弃预览。

也可以导入 ZIP 主题包，在「我的主题」中重命名、导出或删除；主题包可以携带 WebM/MP4 动态背景视频和可选环境音，视频在动效开启时静音循环播放。主题包格式、视频与素材限制、素材来源与接口见 [场景与主题包](docs/theme-packs.md)。

<details>
<summary>场景图和生成提示词</summary>

当前「雨窗」的横屏背景为 `frontend/src/assets/rain-room.jpg`。原版雨窗和夜间图书馆场景图分别保存为 `frontend/src/assets/rain.jpg` 和 `frontend/src/assets/library.jpg`。这些场景图由内置 imagegen 生成。

`rain-room.jpg`

> Use case: photorealistic-natural. Create an original, wide 16:9 full-screen background for a calm personal study room web app. Eye-level from behind a walnut study desk, framed by an expansive rain-streaked picture window filling the entire upper two-thirds. Beyond the glass, layered dense evergreen forest recedes into a misty valley after a rain shower, with a little warm evening sunlight filtering through the clouds. A glowing vintage brass desk lamp on the left third, a small stack of books on the right third, a ceramic mug and open blank notebook. Keep the upper middle open and low contrast behind a circular timer overlay. Bottom quarter shows the desk surface with believable spatial depth. Cinematic natural editorial interior photography, crisp rain droplets, real wood grain, cool fern greens contrasted with gentle amber lamplight, atmospheric but sufficiently luminous and detailed. Full landscape framing with desk objects inset from the edges so they remain visible on desktop. Image only. No people, words, text, watermark, logos, or interface elements.

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

打开 [Docker 自习室](http://127.0.0.1:18119/)。可用 `ZHIJING_DOCKER_PORT` 调整宿主机端口。Docker 自习室使用独立的 `study-data` 卷保存 SQLite 和导入的主题包（`/data/themes/`），浏览器歌单随访问地址保存。运行 `docker compose down` 可停止容器并保留卷。

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

打开 [本地自习室](http://127.0.0.1:18081/)。默认数据目录为 `.data/`，SQLite 为 `.data/study.sqlite3`，导入主题在 `.data/themes/`，备份在 `.data/backups/`；可用 `ZHIJING_STUDY_DATA_DIR` 统一调整数据目录。需要写入 Obsidian 时，在 `.env` 用 `ZHIJING_STUDY_OBSIDIAN_DIR` 指定一个已存在的 Vault 子目录，保存配置后重启服务。Windows 路径可以使用正斜杠。

前端开发时，可让上述 FastAPI 服务继续运行，在另一个终端执行 `npm.cmd --prefix frontend run dev`，通过 Vite 的本地地址访问界面。

## 数据、备份与接口类型

服务启动时通过 `PRAGMA user_version` 执行数据库迁移；默认数据目录包含 SQLite、主题包和备份。备份会生成一致的 SQLite 快照与全部主题素材：

```powershell
uv run --locked --no-sync python dev/backup.py
uv run --locked --no-sync python dev/backup.py --output D:/backups/zhijing.zip
```

Docker 版备份到数据卷，再复制到宿主机：

```powershell
docker compose exec -e PYTHONPATH=/app/backend zhijing python -m zhijing.backup --output /data/backups/zhijing.zip
docker compose cp zhijing:/data/backups/zhijing.zip .
```

### 从备份恢复

备份是自包含 ZIP（`manifest.json`、SQLite 快照和全部主题素材），可以直接恢复到任意数据目录。先查看内容，再决定是否覆盖：

```powershell
uv run --locked --no-sync python dev/restore.py D:/backups/zhijing.zip --inspect
uv run --locked --no-sync python dev/restore.py D:/backups/zhijing.zip
```

恢复到当前数据目录时，如果里面已经有笔记，命令会拒绝执行并提示加 `--force`；加 `--force` 后原有数据库和主题目录会改名为 `<文件名>.pre-restore-<时间戳>` 保留在数据目录里，不会直接删除。恢复前请先停止正在运行的服务，恢复后重新启动即可。Docker 版可以先把备份复制进容器再执行：

```powershell
docker compose cp zhijing.zip zhijing:/data/restore.zip
docker compose exec -e PYTHONPATH=/app/backend zhijing python -m zhijing.restore --inspect /data/restore.zip
docker compose exec -e PYTHONPATH=/app/backend zhijing python -m zhijing.restore --force /data/restore.zip
```

后端接口类型由 OpenAPI 生成到前端，修改接口后执行：

```powershell
uv run --locked --no-sync python dev/export_openapi.py
npm.cmd --prefix frontend run gen:api
```

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
uv run --locked --no-sync ruff check .
uv run --locked --no-sync pytest -q
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run format:check
npm.cmd --prefix frontend run test:unit
npm.cmd --prefix frontend run build
```

Python 测试使用临时 SQLite 文件和合成主题包，无需启动外部数据库。备份与恢复各有一组回归用例（`tests/test_backup.py`、`tests/test_restore.py`），覆盖清单校验、路径穿越、覆盖前保留旧数据和恢复 CLI。CI 在 [.github/workflows/ci.yml](.github/workflows/ci.yml) 中执行同一组检查，并校验 OpenAPI 快照与生成的 TS 类型没有漂移。前期与 LearnHub 旧编辑器的兼容验证见 [试点记录](docs/learnhub-pilot.md)，主题包的制作和验收见 [场景与主题包](docs/theme-packs.md)，历次交付的改动与验收输出见 [实施与验收记录](docs/implementation-records.md)。

项目约定和两份 Markdown 技能源自 LearnHub `767b4aa`，相关材料适用 [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)。

Required Notice: Copyright (c) 2026 QiuLf
