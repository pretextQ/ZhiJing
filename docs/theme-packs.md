# 场景与主题包

知径内置六款自习室场景，也可以导入自己的 ZIP 主题包。本文说明内置素材来源、主题包格式、导入限制、接口和验收方法。开发计划见 [后续开发计划](development-plan.md)。

## 一、内置主题

| ID | 名称 | 素材 | 来源与授权 |
| --- | --- | --- | --- |
| `rain` | 雨窗 | [rain.jpg](../frontend/src/assets/rain.jpg) | 项目 imagegen 生成，生成提示词见 [README](../README.md)「场景图和生成提示词」 |
| `library` | 夜间图书馆 | [library.jpg](../frontend/src/assets/library.jpg) | 项目 imagegen 生成，生成提示词见 [README](../README.md)「场景图和生成提示词」 |
| `morning` | 清晨书桌 | [morning.jpg](../frontend/src/assets/morning.jpg) | 项目原创合成插画，由 [generate_theme_assets.py](../dev/generate_theme_assets.py) 生成 |
| `seaside` | 海边木屋 | [seaside.jpg](../frontend/src/assets/seaside.jpg) | 同上 |
| `train` | 暮色列车 | [train.jpg](../frontend/src/assets/train.jpg) | 同上 |
| `pixel` | 像素夏夜 | [pixel.jpg](../frontend/src/assets/pixel.jpg) | 同上 |

四张新图是可供发布的原创合成素材，不含第三方摄影或字体；随项目按 PolyForm Noncommercial License 1.0.0 发布。如需换成真实摄影，按 2172×724（约 3:1）的同名 JPEG 替换并重新构建前端即可。可运行 `python dev/generate_theme_assets.py` 重新生成（需要 Pillow 与 numpy）。

## 二、主题包格式

主题包是 ZIP 文件，根目录必须放 UTF-8 编码的 `theme.json`。清单里的文件名是包内相对路径，支持中文文件名和子目录。

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

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schemaVersion` | 是 | 当前只支持整数 `1` |
| `name` | 是 | 去首尾空白后 1–60 个字符，显示在主题卡片上 |
| `background` | 是 | 首页背景图，支持 JPEG、PNG、WebP |
| `cover` | 否 | 卡片封面图；省略时使用 `background` |
| `ambient` | 否 | 可选环境音，支持 MP3、Ogg；导入后在「声音设置 → 环境音」出现「主题环境音」 |

限制与校验：

- ZIP 文件不超过 32 MiB，展开后总大小不超过 64 MiB，最多 32 个条目。
- 只接受普通文件；拒绝绝对路径、`..`、反斜杠、盘符、空路径段、符号链接和加密条目。
- 图片与音频按扩展名和文件魔数双重校验；引用文件必须在包内真实存在。
- `theme.json` 必须位于 ZIP 根目录；引用路径按正斜杠 `/` 相对定位。
- 同一份 ZIP（按字节 sha256）重复导入不会产生新卡片，而是返回已有主题卡片。

制作示例（PowerShell，在主题包目录内执行）：

```powershell
Compress-Archive -Path theme.json,cover.jpg,background.webp,rain.mp3 -DestinationPath ../my-study-room.zip -Force
```

注意不要把外层文件夹一起压进 ZIP，否则 `theme.json` 不在根目录，导入会失败。

## 三、使用流程

1. 打开自习室首页底部的「场景」，内置主题和「我的主题」显示在同一个面板。桌面端三列两行，窄屏自动改为两列或一列。
2. 点击卡片预览：首页背景切换为预览图，当前已应用主题保留，卡片标记「预览」。
3. 点击「应用此场景」保存选择并关闭面板，刷新后恢复；按 Escape 或关闭按钮放弃预览并回到已应用场景。
4. 点击「导入主题包」选择 ZIP。导入成功后卡片出现在「我的主题」，并立即进入预览；失败时面板内显示具体原因。
5. 自定义主题卡片上的删除按钮需要二次确认。删除当前正在使用的主题后回到「雨窗」；删除其他主题不影响当前场景。
6. 自定义主题环境音在「声音」面板的「环境音」下拉框中选择，音量与白噪音共用；本地歌单独立控制。

主题选择保存在浏览器 `localStorage` 的 `zhijing:scene`；自定义主题的文件保存在服务端 SQLite 数据目录，刷新页面或重建 Docker 容器都不会丢失（使用同名数据卷时）。

## 四、存储与接口

自定义主题存放在 `<SQLite 数据目录>/themes/<12 位十六进制主题 ID>/`，可用 `ZHIJING_STUDY_THEME_DIR` 覆盖。本地默认在 `.data/themes/`，Docker 版在 `/data/themes/`，随 `study-data` 卷持久化。目录中包含解压后的素材、原始 `theme.json` 和记录上传包哈希的 `.archive-sha256`。

| 方法与路径 | 说明 |
| --- | --- |
| `GET /api/study/themes` | 列出全部自定义主题卡片 |
| `POST /api/study/themes` | 请求体为 ZIP 字节，`Content-Type: application/zip`；成功返回主题卡片 |
| `GET /api/study/themes/{id}/assets/{path}` | 读取经校验的封面、背景或环境音 |
| `DELETE /api/study/themes/{id}` | 删除自定义主题，成功返回 204 |

接口与自习室 API 一样只允许本机地址和同源页面访问，响应不缓存。错误响应为 `{"detail": "中文原因"}`，前端直接展示。

## 五、验收

前端构建加后端测试：

```powershell
npm.cmd --prefix frontend run build
uv run --locked --no-sync pytest -q
```

浏览器验收会启动独立实例，检查六款内置场景、预览/应用/刷新恢复、键盘与 320px、ZIP 导入/重复导入/无效包、主题环境音播放、删除回退，以及看课笔记往返。首次使用先准备 Playwright（见 [仓库根目录 README](../README.md) 的测试说明）：

```powershell
uv pip install --target .dev/browser-deps playwright==1.65.2
$env:PYTHONPATH = (Resolve-Path .dev/browser-deps).Path
uv run --locked --no-sync python -m playwright install chromium
uv run --locked --no-sync python dev/verify_themes.py
```

Docker 验收使用独立项目名和端口，自动导入合成 ZIP、重建容器并检查同一数据卷上的主题与素材：

```powershell
uv run --locked --no-sync python dev/verify_themes_docker.py
```

脚本内部等价于：

```powershell
$env:ZHIJING_DOCKER_PORT = '18129'
docker compose -f compose.yaml -p zhijing-theme-qa up -d --build --wait
# 导入合成 ZIP、验证素材，然后：
docker compose -f compose.yaml -p zhijing-theme-qa up -d --force-recreate --wait
docker compose -f compose.yaml -p zhijing-theme-qa down -v
```

2026-11-16 的验收结果：后端 84 项测试通过；前端类型检查与构建通过；浏览器脚本与 Docker 脚本均 PASS，重建容器后背景与可选音频仍可读取；无效 ZIP 返回 422 中文原因且不改变主题库。
