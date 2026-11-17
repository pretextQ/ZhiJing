# 知径后续开发计划书

基线提交为 `f25cec4`。知径面向个人使用与 Docker 自部署。当前自习室首页提供沉浸场景、专注计时和目标，右上角进入独立的「看课笔记」。看课笔记支持 B 站、SQLite 自动保存和 Obsidian 导出。下一版优先补齐场景选择与主题包导入，之后再扩展通用笔记与资料库。

开发范围与取舍以 [项目基调](project-charter.md) 为准；开源不改变单人自用的定位。

## 一、下一版目标

打开自习室后，可以从底部「场景」入口查看六款内置主题，也可以从电脑导入自己的主题包。选中卡片即可预览，点击「应用」后切换场景，下次打开恢复上次选择。场景切换期间，当前专注计时继续运行。从首页进入或退出「看课笔记」时，保持各课程的编辑状态、撤销记录和草稿。

| 内置主题 | 画面方向 | 素材状态 |
| --- | --- | --- |
| 雨窗 | 灰绿树林、落雨玻璃、书桌 | 沿用现有场景图 |
| 夜间图书馆 | 深木书架、暖色台灯 | 沿用现有场景图 |
| 清晨书桌 | 晨光、绿植、浅木桌 | 待制作 |
| 海边木屋 | 窗外海面、明亮木屋 | 待制作 |
| 暮色列车 | 晚霞、车窗、暖色座椅 | 待制作 |
| 像素夏夜 | 像素星空、夜色田野 | 待制作 |

桌面端有足够宽度时，六款内置主题以三列两行的大图卡片展示。窄屏按可用宽度改成两列或一列。导入的主题与内置主题出现在同一个选择面板，通过「我的主题」标题找到。首版交付静态背景、封面与可选环境音。动态背景和主题导出列入后续候选功能，主题包通过公开的格式说明分享。

## 二、用户流程

1. **选场景。** 打开底部场景面板，选一张卡片开始预览。预览覆盖首页背景，并保留当前已应用的主题。点击「应用」保存选择，关闭或按 Escape 恢复预览前的画面，焦点回到场景入口。
2. **导入主题。** 从场景面板选择一个 ZIP 文件。校验通过后，主题写入本机主题库，作为一张新卡片进入预览。用户可以立即应用，也可以留在主题库稍后使用。校验失败时显示具体原因，比如缺少背景文件或清单版本不受支持。
3. **用主题环境音。** 包内音频在声音设置中显示为当前主题的可选环境音。用户可主动播放、暂停和调音量。本地歌单与环境音分别控制。
4. **管理已导入主题。** 用户可以删除自己的主题。删除当前使用的主题后，回到雨窗。相同 ZIP 的重试或重复导入打开已存在的卡片。

## 三、主题包与存储

主题包为 ZIP，根目录放置 UTF-8 编码的 `theme.json`。下面的文件名是合成示例，可以替换成包内相对路径，支持中文文件名。

```text
my-study-room.zip
├── theme.json
├── cover.jpg
├── background.webp
└── rain.mp3
```

```json
{
  "schemaVersion": 1,
  "name": "我的雨天书桌",
  "background": "background.webp",
  "cover": "cover.jpg",
  "ambient": "rain.mp3"
}
```

- `schemaVersion`、`name` 和 `background` 为必填字段。`cover` 可省略，卡片直接使用背景图。`ambient` 可省略。第一版图片支持 JPEG、PNG 和 WebP，环境音支持 MP3 和 Ogg。
- 内置主题使用稳定 ID，沿用已有的 `rain` 和 `library`。前端集中维护主题目录和卡片组件，继续用当前浏览器的场景偏好保存所选 ID。
- 自定义主题由 FastAPI 管理，每个主题使用应用生成的 ID。素材和清单存放在 SQLite 数据目录下的 `themes/` 子目录，Docker 版落在既有数据卷的 `/data/themes/`。首版通过清单和文件目录读取主题，现有笔记数据库继续管理课程和正文。
- 导入时先检查包大小、文件数与展开体积，再校验 JSON 和引用的媒体文件。路径必须位于包内，按清单逐个提取已校验的普通文件。使用同卷临时目录写入，全部通过后再发布到主题库。读取资源通过主题 ID 和清单里的已校验条目定位，失败时清理临时文件。
- 上限可先按 ZIP 32 MiB、展开 64 MiB、32 个归档条目设置，作为可调的实现默认值。以四款新增内置图和合成主题包的实际大小复核，并在导入页说明当前限制。

## 四、开发任务与验收

每次交给开发代理一个阶段。先读 [AGENTS.md](../AGENTS.md) 和本计划，阶段结束时汇报改动、执行过的验证和待验证项。代码审查以实际的差异和验收结果为准。

### 第一步 · 场景选择面板

从 [App.vue](../frontend/src/App.vue) 抽出主题目录与选择面板，接上现有背景和浏览器偏好。准备四款新增原创或可再发布的视觉素材，记录来源，交付六款完整主题。素材未齐时可以先用现有两款检查交互，内部测试使用合成素材。场景面板有键盘焦点管理，深浅色和 320px 宽度下操作可用。

### 第二步 · ZIP 导入和持久化

在 FastAPI 增加主题模块，提供列出、导入、读取经校验的素材与删除自定义主题的接口。用临时目录和合成包测试有效导入、重复上传、缺文件、非法归档路径、超出限制和中途失败。首次导入功能对已有数据卷可直接增加主题目录。

### 第三步 · 导入界面与主题环境音

串起「导入 → 预览 → 应用」和删除后的回退流程。复用 [SoundPanel.vue](../frontend/src/SoundPanel.vue) 放置主题环境音控件。在两个页面间往返，验证专注计时、播放中的背景音、课程草稿和撤销记录。补充一段 ZIP 制作说明，便于用户自己制作并分享主题包。

### 发布前检查

- [x] 六款内置主题都能预览和应用，刷新后恢复选中的场景。鼠标和键盘都能导入、预览、应用与关闭面板。
- [x] 合成 ZIP 能在 Docker 版导入。用同一数据卷重建容器后，主题仍可选，背景和可选音频仍可加载。
- [x] 无效 ZIP 给出原因，主题库和当前场景处于导入前的状态。
- [x] 首页的「看课笔记」入口和 `/courses` 直达都可用。分 P、续播点、笔记保存和 Obsidian 导出通过回归验收。
- [x] 记录六款内置素材的来源与再发布授权。GitHub 示例、截图、测试包和测试 Vault 使用合成数据。

按 [本地启动说明](../README.md#本地启动) 准备依赖后，在仓库根目录运行前端构建和后端测试。

```powershell
npm.cmd --prefix frontend run build
uv run --locked --no-sync pytest -q
```

在单独的 PowerShell 会话启动 Docker 验收实例。显式指定基础 Compose 文件，使用独立端口和数据卷。验收 Obsidian 时单独挂载一个合成 Vault。

```powershell
$env:ZHIJING_DOCKER_PORT = '18129'
docker compose -f compose.yaml -p zhijing-theme-qa up -d --build --wait
```

从本机 `http://127.0.0.1:18129/` 验收。导入合成 ZIP 后，重复运行上面的启动命令并加上 `--force-recreate`，确认同一数据卷可以恢复主题。验收结束后执行 `docker compose -f compose.yaml -p zhijing-theme-qa down -v`。

## 五、后续路线

| 顺序 | 开发主题 | 首次交付 |
| --- | --- | --- |
| 1 | 场景与主题包 | 完成上述三个阶段，让用户能用自带素材打造自习室。 |
| 2 | 通用笔记与目录 | 增加独立笔记实体，可以关联课程或资料。配套 SQLite 版本迁移和备份恢复，使用旧版数据卷验证原有课程正文与续播点。目录按项目约定使用路径、返回导航和同一资源列表。 |
| 3 | 资料库与检索 | 支持组织和查找本地资料，先交付文件入库、全文搜索和可打开的来源。遇到耗时的解析或 OCR，再加入可查看进度的后台任务。 |
| 4 | 智能体学习工作流 | 复用现有流式润色入口，逐步支持基于当前笔记与已选资料的问答和整理，结果可预览再写入。 |

开源发布准备可以与主题包并行。整理自部署和升级备份说明，在 GitHub Actions 验证 Python 测试、前端构建和 Docker 启动，并按 [现有许可说明](../README.md) 核对 LearnHub 迁入材料和新场景素材的发布范围。

## 可交给开发代理的第一条任务

> 读取 `AGENTS.md` 和 `docs/development-plan.md`，完成第四节的「第一步 · 场景选择面板」。先检查现有主题 ID、首页场景入口和深浅色样式，再实现大图预览与应用。优先复用已有代码，保留专注计时和看课笔记的往返流程。使用合成数据检查桌面、320px 窄屏、键盘和刷新恢复。完成后列出改动、实际运行的验证命令和待补的场景素材。

## 实施与验收记录（2026-11-16）

在提交 `a8c2546` 基础上，按第四节的三个开发阶段完成场景与主题包开发，并勾选上节发布前检查。

### 交付内容

- 后端：[services/themes.py](../backend/zhijing/services/themes.py) 提供自定义主题导入、列表、素材读取与删除；[settings.py](../backend/zhijing/settings.py) 支持 `ZHIJING_STUDY_THEME_DIR`；[main.py](../backend/zhijing/main.py) 挂载路由。ZIP 32 MiB、展开 64 MiB、32 条目限制，校验清单、路径、符号链接、加密条目和素材魔数，暂存目录加原子发布，同包 sha256 去重。
- 前端：[themes.ts](../frontend/src/themes.ts) 内置六款主题并封装接口，[ThemePanel.vue](../frontend/src/components/ThemePanel.vue) 实现 3/2/1 列场景面板、预览/应用/删除/导入与键盘焦点，[SoundPanel.vue](../frontend/src/components/SoundPanel.vue) 增加主题环境音，[styles/themes.css](../frontend/src/styles/themes.css) 覆盖 320px、深浅色和粘性操作栏。
- 素材：[morning.jpg](../frontend/src/assets/morning.jpg)、[seaside.jpg](../frontend/src/assets/seaside.jpg)、[train.jpg](../frontend/src/assets/train.jpg)、[pixel.jpg](../frontend/src/assets/pixel.jpg)，由 [generate_theme_assets.py](../dev/generate_theme_assets.py) 生成的原创合成插画；来源与授权见 [场景与主题包](theme-packs.md)。
- 测试与验收：[test_themes.py](../tests/test_themes.py) 新增 50 项用例；[verify_themes.py](../dev/verify_themes.py) 与 [verify_themes_docker.py](../dev/verify_themes_docker.py) 提供浏览器和 Docker 验收脚本。
- 文档：[场景与主题包](theme-packs.md)、[README](../README.md)。

### 实际验证

```text
uv run --locked --no-sync pytest -q
  84 passed, 1 warning（原有 34 项 + 主题 50 项）

npm.cmd --prefix frontend run build
  vue-tsc --noEmit 通过；vite build 成功，dist 包含六张主题图

$env:PYTHONPATH=(Resolve-Path .dev/browser-deps).Path
uv run --locked --no-sync python dev/verify_themes.py
  PASS：六款内置、预览/应用/刷新恢复、键盘、ZIP 导入/重复/无效包、320px、深色、
        主题环境音播放、专注计时与课程草稿/撤销往返、删除回退雨窗

uv run --locked --no-sync python dev/verify_themes_docker.py
  PASS：独立项目 zhijing-theme-qa / 端口 18129 导入合成包，重建容器后同一数据卷
        仍返回主题与素材；无效包 422；删除后主题库为空；结束执行 down -v

$env:PYTHONPATH=(Resolve-Path .dev/browser-deps).Path
uv run --locked --no-sync python .dev/verify_study_mvp.py
  PASS：专注计时、导航、音频、场景、深浅色、320px、课程草稿/撤销与 Obsidian 导出
```

### 待验证与后续

- 四张新增场景图是项目原创合成插画，可按 [场景与主题包](theme-packs.md) 替换为有授权的真实摄影；替换后重新构建前端即可。
- 动态背景、主题包导出与重命名已在下一轮完成（见下方记录）；主题库排序仍在后续候选中。
- 主题限制已可配置（见下一轮记录）。
- 本机已存在的旧 `zhijing` 容器仍运行旧镜像；需要更新时在仓库根目录执行 `docker compose up -d --build`。

## 动态背景与主题管理实施记录（2026-11-16）

在上一轮场景与主题包交付后，继续完成后续候选中的动态背景、主题包导出/重命名和主题限制可配置化。

### 交付内容

- 动态背景：主题包清单新增可选 `backgroundVideo`（WebM/MP4，魔数校验），首页在动效开启时静音循环播放视频，静态背景作为封面和失败回退；内置六款主题使用缓慢平移/缩放动效，场景面板新增「背景动效」开关（`zhijing:motion`），系统要求减少动效时自动停用。
- 主题管理：`PATCH /api/study/themes/{id}` 重命名（原子更新 `theme.json`）；`GET /api/study/themes/{id}/export` 导出包含清单与全部引用素材的 ZIP，支持中文下载名；自定义主题卡片增加导出、重命名工具栏，重命名支持 Enter/失焦保存和 Escape 取消。
- 可配置限制：`ZHIJING_STUDY_THEME_MAX_ARCHIVE_MB`、`_MAX_EXPANDED_MB`、`_MAX_ENTRIES` 控制导入上限，`GET /api/study/themes/limits` 返回实际值，面板显示当前限制。
- 测试素材：[scene-loop.webm](../tests/fixtures/scene-loop.webm) 为 3 秒合成动态背景，仅用于浏览器和接口验收。

### 实际验证

```text
uv run --locked --no-sync pytest -q
  122 passed, 1 warning（原 84 项 + 视频/重命名/导出/限制新增 38 项）
npm.cmd --prefix frontend run build
  vue-tsc --noEmit 通过；vite build 成功
$env:PYTHONPATH=(Resolve-Path .dev/browser-deps).Path
uv run --locked --no-sync python dev/verify_themes.py
  PASS：动效开关与减少动效、动态视频播放、重命名、导出 ZIP 内容、限制提示、320px、深色、
        预览/应用/刷新、导入/重复/无效包、主题环境音、计时与课程草稿往返、删除回退
uv run --locked --no-sync python dev/verify_themes_docker.py
  PASS：导入含视频包、重命名与导出、重建容器后素材仍可读、无效包 422、删除后清空
$env:PYTHONPATH=(Resolve-Path .dev/browser-deps).Path
uv run --locked --no-sync python .dev/verify_study_mvp.py
  PASS：专注计时、导航、音频、场景、深浅色、320px、课程草稿/撤销与 Obsidian 导出
```

### 仍在范围外

- 真实摄影或视频素材的授权替换、主题库排序与搜索、动态背景视频的转码/压缩均未在本次实现。
- 主题限制目前为整数 MiB/条目数，尚未提供管理界面；通过环境变量或 `.env` 调整。

## 阶段1基础设施实施记录（2026-11-16）

按架构评审的阶段1，完成数据库迁移、后端分层、数据目录/备份、前端路由与状态、质量工具和 OpenAPI 类型。

### 后端

- [infra/db.py](../backend/zhijing/infra/db.py)：启动时按 `PRAGMA user_version` 迁移（当前 v1，兼容旧库），启用 WAL、外键和 busy_timeout；不再在每次请求建表。
- [settings.py](../backend/zhijing/settings.py)：新增 `ZHIJING_STUDY_DATA_DIR`；数据目录统一推导 SQLite、`themes/` 与 `backups/`。
- [backup.py](../backend/zhijing/backup.py) 与 [dev/backup.py](../dev/backup.py)：生成含 manifest、SQLite 一致性快照和主题素材的 ZIP，原子写出；支持 `python -m zhijing.backup`。
- 目录分层：[api/](../backend/zhijing/api/) 薄路由、[services/](../backend/zhijing/services/) 业务、[infra/](../backend/zhijing/infra/) 数据库、[domain/](../backend/zhijing/domain/) 模型、[legacy/](../backend/zhijing/legacy/) 润色兼容层；共享的本地访问依赖在 `api/deps.py`。
- [tests/test_db.py](../tests/test_db.py)、[tests/test_backup.py](../tests/test_backup.py) 覆盖迁移幂等、旧库保留、快照与备份内容。

### 前端与工具

- vue-router + Pinia：[router/index.ts](../frontend/src/router/index.ts)、[stores/study.ts](../frontend/src/stores/study.ts)、[stores/themes.ts](../frontend/src/stores/themes.ts)；[App.vue](../frontend/src/App.vue) 只保留布局与面板开关，ThemePanel 独立成组件。
- 样式拆为 [styles/](../frontend/src/styles/) 下 tokens/base/layout/themes/courses，视觉保持不变。
- Vitest 32 项、ESLint、Prettier：脚本为 `lint`、`format:check`、`test:unit`；生成类型 [api/schema.d.ts](../frontend/src/api/schema.d.ts) 来自 [openapi.json](../frontend/openapi.json)。
- [.github/workflows/ci.yml](../.github/workflows/ci.yml)：后端 ruff + pytest + OpenAPI 快照校验；前端类型生成校验、lint、format、单测和构建。

### 实际验证

```text
uv run --locked --no-sync ruff check .                 All checks passed
uv run --locked --no-sync pytest -q                    135 passed
uv run --locked --no-sync python dev/export_openapi.py  12 paths / 12 schemas
npm.cmd --prefix frontend run lint                     eslint 0 error
npm.cmd --prefix frontend run format:check             All matched files use Prettier code style
npm.cmd --prefix frontend run test:unit                32 passed
npm.cmd --prefix frontend run build                    vue-tsc + vite build 通过
python dev/verify_themes.py                            PASS（含动效/视频/导入导出/计时草稿往返）
python .dev/verify_study_mvp.py                        PASS（计时、音频、场景、320px、Obsidian 导出）
python dev/verify_themes_docker.py                     PASS（导入/重建/导出/删除）
```

### 使用说明

- 本机备份：`uv run --locked --no-sync python dev/backup.py [--output ...]`；Docker 内用 `docker compose exec -e PYTHONPATH=/app/backend zhijing python -m zhijing.backup`。
- 修改接口后：`uv run --locked --no-sync python dev/export_openapi.py` 然后 `npm.cmd --prefix frontend run gen:api`，CI 会校验快照未漂移。
- `dev/backup.py` 不进入 Docker 镜像；容器内使用 `python -m zhijing.backup`。

## 自习室首页重做与单人基调实施记录（2026-11-17）

在提交 `a8c2546` 之后的主题包与基础设施之上，按新的[项目基调](project-charter.md)重做自习室首页，并据此重做外部调研。

### 交付内容

- 基调与调研：[project-charter.md](project-charter.md) 确立单人自用定位与第 4.3 节非目标表；[online-study-room-solo-research.md](online-study-room-solo-research.md) 重做调研，前两份多人方向调研（[布局与设计](online-study-room-research.md)、[海外产品](online-study-room-overseas-products.md)）在文首标注作废，仅作资料留档。
- 首页工作台：[RoomView.vue](../frontend/src/views/RoomView.vue)、[FocusTimer.vue](../frontend/src/components/FocusTimer.vue)、[App.vue](../frontend/src/App.vue) 与 [styles/room.css](../frontend/src/styles/room.css) 收敛为一屏沉浸版式：场景背景铺满、计时器居中、待办与今日专注在底部、声音面板在右侧；沉浸模式保留小计时器与场景 / 声音入口。
- 场景动效：[RainWindow.vue](../frontend/src/components/RainWindow.vue) 为雨窗增加分层雨滴，仍受「背景动效」开关与系统减少动效约束。
- 计时圆环：[styles/room.css](../frontend/src/styles/room.css) 用单层 conic 渐变加径向遮罩画出 1.5px 细环，轨道与进度共用一条渐变；沉浸侧栏过窄时回落为细进度线，没有逐秒动画。

### 实际验证

```text
uv run --locked --no-sync ruff check .                 All checks passed
uv run --locked --no-sync pytest -q                    135 passed, 1 warning
npm.cmd --prefix frontend run lint                     eslint 0 error
npm.cmd --prefix frontend run format:check             All matched files use Prettier code style
npm.cmd --prefix frontend run test:unit                35 passed（5 个文件）
npm.cmd --prefix frontend run build                    vue-tsc --noEmit 与 vite build 通过
$env:PYTHONPATH=(Resolve-Path .dev/browser-deps).Path
uv run --locked --no-sync python dev/verify_themes.py
  PASS：六款内置、雨滴动效、动效开关与减少动效、预览/应用/刷新、键盘、ZIP 导入/重复/无效包、
        视频播放、重命名/导出、限制提示、320px、深色、主题环境音、计时与课程草稿往返、删除回退
uv run --locked --no-sync python dev/verify_themes_docker.py
  PASS：含背景、视频与环境音的合成包导入，重命名与导出，重建容器后同一数据卷仍可读，
        无效包 422，删除后主题库为空，结束执行 down -v
docker compose up -d --wait
  重建本机容器后，18119 提供的 index/css 与仓库构建产物哈希一致，样式含 .timer-ring 与 conic-gradient
```

### 待验证与后续

- 单人调研第 9 节列出的五件可立即做的事，目前只落地「计时器去掉逐秒动画」一项；四轮后自动长休息、时长三档（25/5、50/10、10/3）、环境音按功能分类、环境音 300–800 ms 淡入均未实现。
- 主题库排序与搜索、真实摄影素材替换、动态背景视频转码仍在范围外。
- 旧 `zhijing` 容器需要更新时，在仓库根目录执行 `docker compose up -d --build`。

