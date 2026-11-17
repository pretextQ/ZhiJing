# 知径实施与验收记录

> 这里保存每次交付的改动清单、实际运行的验证命令与输出，以及当时明确留下的待办。
> 它只记录**已经发生的事**，不是路线图，也不约束后续方向，后续设计由项目负责人直接决定。
> 开发范围与取舍仍以[项目基调](project-charter.md)为准。

| 日期 | 交付 |
| --- | --- |
| 2026-11-16 | 场景与主题包：六款内置场景、ZIP 导入、主题环境音 |
| 2026-11-16 | 动态背景、主题包导出与重命名、可配置限制 |
| 2026-11-16 | 阶段1基础设施：迁移、分层、备份、路由与 CI |
| 2026-11-17 | 自习室首页重做、雨滴动效、计时圆环、单人基调与调研 |
| 2026-11-17 | 环境音记忆、备份恢复、README 备份路径修正 |

## 实施与验收记录（2026-11-16）

在提交 `a8c2546` 基础上，按「场景与主题包」三个阶段完成开发，并完成当时列出的发布前检查。

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

在上一轮场景与主题包交付后，继续完成动态背景、主题包导出/重命名和主题限制可配置化。

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

- 单人调研第 9 节列出的五件可立即做的事，截至本轮只落地「计时器去掉逐秒动画」一项；四轮后自动长休息、时长三档（25/5、50/10、10/3）、环境音按功能分类、环境音 300–800 ms 淡入均未实现。
- 主题库排序与搜索、真实摄影素材替换、动态背景视频转码仍在范围外。
- 旧 `zhijing` 容器需要更新时，在仓库根目录执行 `docker compose up -d --build`。

## 功能完善补齐（2026-11-17）

首页重做后对照功能清单补了三处缺口，均不改变产品形态。

### 交付内容

- 环境音记忆：[SoundPanel.vue](../frontend/src/components/SoundPanel.vue) 把所选环境音写入 `zhijing:noise`，刷新、跨页面往返和重启浏览器后恢复并继续播放；启动失败时清回静音，避免下次打开反复重试。
- 备份恢复：[restore.py](../backend/zhijing/restore.py) 与 [dev/restore.py](../dev/restore.py) 校验 manifest、条目路径与 SQLite 完整性后，先在数据目录的临时目录解包，再替换数据库与主题目录；目标已有笔记时默认拒绝，加 `--force` 会把旧数据保留为 `.pre-restore-<时间戳>`。容器内可直接 `python -m zhijing.restore`。
- 文档修正：[README](../README.md) 的备份路径示例此前含有被吞掉的 `\b` 转义，实际会写到当前目录；现改为 `D:/backups/zhijing.zip`，并补充「从备份恢复」一节与备份 / 恢复测试说明。

### 实际验证

```text
uv run --locked --no-sync ruff check .                 All checks passed
uv run --locked --no-sync pytest -q                    146 passed, 1 warning（原 135 项 + 恢复 11 项）
npm.cmd --prefix frontend run lint                     eslint 0 error
npm.cmd --prefix frontend run format:check             All matched files use Prettier code style
npm.cmd --prefix frontend run test:unit                38 passed（原 35 项 + 环境音 3 项）
npm.cmd --prefix frontend run build                    vue-tsc 与 vite build 通过
```

另外做了两组人工验收：本机 CLI 备份 → `--inspect` → 覆盖恢复，第二次恢复不带 `--force` 被正确拒绝；Docker 版把备份 `cp` 进容器后执行 `python -m zhijing.restore --force`，旧数据库与主题目录按时间戳保留，随后手工还原回测试前数据。浏览器端确认环境音选择写入 `localStorage`、刷新后保持「播放中」。

### 待验证与后续

- 恢复只针对备份 ZIP，不支持合并或选择性恢复单个主题；需要时从 `.pre-restore-*` 目录里手工取回。
- 恢复期间需要手动停止服务，避免正在运行的进程仍持有旧数据库句柄。

## 内置场景扩充（2026-11-17）

按本机壁纸收藏新增五款内置场景，并把「森林小船」设为默认皮肤。

### 交付内容

- 素材：`forest.jpg`、`palms.jpg`、`whitecat.jpg` 由原图缩到 2400px 宽并以 quality 84 重编码；`water-loop.mp4`（2850×1604 → 1600×900，CRF 28）与 `anime-loop.mp4`（2884×2160@60 → 1600×900@24，CRF 30）为循环视频，配套 `water-poster.jpg`、`anime-poster.jpg` 作静态回退。
- 代码：[themes.ts](../frontend/src/themes.ts) 新增 `palms`、`whitecat`、`water`、`anime` 四款，并把 `forest` 置于首位、`DEFAULT_THEME_ID` 改为 `forest`；[stores/themes.ts](../frontend/src/stores/themes.ts) 的 `sceneVideoUrl` 不再排除内置主题，内置视频与导入包视频走同一条静音循环路径。
- 授权：[theme-packs.md](../docs/theme-packs.md) 已标注五款新素材来自本机壁纸收藏、来源与授权未核实，其中 `anime` 含第三方版权内容，仅建议本机自用。

### 实际验证

```text
uv run --locked --no-sync ruff check .                 All checks passed
npm.cmd --prefix frontend run lint                     eslint 0 error
npm.cmd --prefix frontend run format:check             All matched files use Prettier code style
npm.cmd --prefix frontend run test:unit                39 passed（原 38 项 + 默认皮肤 1 项）
npm.cmd --prefix frontend run build                    vue-tsc 与 vite build 通过
uv run --locked --no-sync python dev/verify_themes.py
  PASS：11 款内置、雨滴动效、动效开关与减少动效、预览/应用/刷新、键盘、ZIP 导入/重复/无效包、
        视频播放（含内置循环视频）、重命名/导出、限制提示、320px、深色、主题环境音、
        计时与课程草稿往返、删除回退
```

浏览器端确认：默认进入即为「森林小船」，场景面板 3 列网格下 11 张卡片全部可解码，水面治愈应用后 `video.scene-video` 静音、循环、可播放且海报图为 `water-poster`。

### 待验证与后续

- 五款新素材的授权问题未解决；若要公开分发仓库，需先替换或摘除。
- 场景面板现在有 11 张卡片、单屏放不下，滚动与分组尚未专门优化。
