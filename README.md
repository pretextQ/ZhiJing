# 知径

FastAPI 后端的首个试点是 `POST /api/ai/polish-stream`。它接收 Markdown 正文和可选的 `mode`，把候选正文流式返回给 LearnHub Vue 编辑器。编辑器继续通过 Spring Boot 保存笔记。对照版本是 LearnHub `767b4aa`。

## 运行 Python 与模拟模型

需要 Python 3.11 或更新版本与 uv。在知径根目录执行以下 PowerShell 命令。模型配置从进程环境和当前目录的 `.env` 读取，进程环境优先。

```powershell
uv sync --locked --default-index https://pypi.org/simple
if (!(Test-Path .env)) { Copy-Item .env.example .env }
uv run --locked --no-sync pytest -q
```

分别在两个终端启动模拟模型和 FastAPI。

```powershell
uv run --locked --no-sync uvicorn dev.mock_model:app --host 127.0.0.1 --port 18082
```

```powershell
uv run --locked --no-sync uvicorn zhijing.main:app --app-dir backend --host 127.0.0.1 --port 18081
```

`ZHIJING_AI_BASE_URL` 填 OpenAI 兼容服务的 API 基址，例如 `http://127.0.0.1:18082/v1`。后端会追加 `/chat/completions`。模型名和密钥分别由 `ZHIJING_AI_MODEL`、`ZHIJING_AI_API_KEY` 提供。默认整轮预算为 270 秒，剩余至少 30 秒才会发起下一段。默认最大输出为 8192 tokens。

## 准备 Vue 与 Spring Boot 基线

从本地 LearnHub 导出指定提交到知径的 `.dev/learnhub`。Vite 配置直接加载这份现有 Vue 应用。

```powershell
New-Item -ItemType Directory .dev/learnhub -Force | Out-Null
git -C D:/projects/LearnHub archive --format=tar --output="$PWD/.dev/learnhub-767b4aa.tar" 767b4aa backend frontend skills
tar -xf .dev/learnhub-767b4aa.tar -C .dev/learnhub
npm --prefix .dev/learnhub/frontend ci
$env:JAVA_HOME = 'C:/Program Files/Java/jdk-21'
mvn -f .dev/learnhub/backend/pom.xml -DskipTests package
```

本机 Maven 可执行文件位于 `D:/software/apache-maven-3.9.16/bin/mvn.cmd`。这次构建遇到 Maven Central 连接超时，使用仅存于 `.dev` 的 Maven 设置访问阿里云公共镜像。

Spring Boot 需要 JDK 21、Maven 和独立的 MySQL 测试库。以下是这次试点所用的本地端口与数据库。将 `$mysqlBin` 改成 MySQL 安装目录下的 `bin`，首次准备时初始化 `.dev/mysql`，随后在单独终端启动。

```powershell
$mysqlBin = 'C:/Program Files/MySQL/MySQL Server 9.7/bin'
New-Item -ItemType Directory .dev/mysql -Force | Out-Null
& "$mysqlBin/mysqld.exe" --no-defaults --initialize-insecure --console "--datadir=$PWD/.dev/mysql"
& "$mysqlBin/mysqld.exe" --no-defaults --console "--datadir=$PWD/.dev/mysql" --bind-address=127.0.0.1 --port=13307 --mysqlx=OFF
```

在另一个终端创建测试库，然后启动 Spring Boot。

```powershell
$mysqlBin = 'C:/Program Files/MySQL/MySQL Server 9.7/bin'
& "$mysqlBin/mysql.exe" --no-defaults --protocol=TCP --host=127.0.0.1 --port=13307 --user=root -e 'CREATE DATABASE zhijing_pilot CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;'
$env:DEEPSEEK_API_KEY = 'synthetic-local-key'
$env:LEARNHUB_SKILLS_DIR = (Resolve-Path .dev/learnhub/skills).Path
$env:JAVA_HOME = 'C:/Program Files/Java/jdk-21'
Set-Location .dev/learnhub/backend
& "$env:JAVA_HOME/bin/java.exe" -jar target/learn-hub-backend-0.0.1-SNAPSHOT.jar `
  --server.address=127.0.0.1 --server.port=18080 `
  '--spring.datasource.url=jdbc:mysql://127.0.0.1:13307/zhijing_pilot?useSSL=false&allowPublicKeyRetrieval=true&characterEncoding=utf8' `
  --spring.datasource.username=root '--spring.datasource.password=' `
  --ai.deepseek.base-url=http://127.0.0.1:18082/v1 --ai.deepseek.model=synthetic-spring `
  --mybatis-plus.configuration.log-impl=org.apache.ibatis.logging.nologging.NoLoggingImpl
```

Spring 初始化后的模型档案优先于启动参数。只在本次测试库中把聊天档案设为模拟模型，并通过 `/api/ai/status` 确认档案生效。

```powershell
$mysqlBin = 'C:/Program Files/MySQL/MySQL Server 9.7/bin'
& "$mysqlBin/mysql.exe" --no-defaults --protocol=TCP --host=127.0.0.1 --port=13307 --user=root --database=zhijing_pilot -e "UPDATE model_profile SET base_url='http://127.0.0.1:18082/v1', model='synthetic-spring', provider='openai', api_key='synthetic-local-key' WHERE purpose='chat';"
Invoke-RestMethod http://127.0.0.1:18080/api/ai/status
```

## 代理与回切

在知径根目录启动 Vite，然后打开 [笔记列表](http://127.0.0.1:15174/notes)。

```powershell
$env:ZHIJING_POLISH_BACKEND = 'python'
node .dev/learnhub/frontend/node_modules/vite/bin/vite.js .dev/learnhub/frontend --config dev/vite.config.mjs --configLoader native
```

试点模式把精确的 `/api/ai/polish-stream` 路径送到 Python，其余 `/api` 路径送到 Spring Boot。要回切，在 Vite 终端按 **Ctrl+C**，设置 `$env:ZHIJING_POLISH_BACKEND = 'spring'` 后执行同一条 Vite 命令。未设置时默认使用 Spring。若端口不同，可设置 `ZHIJING_VITE_PORT`、`ZHIJING_SPRING_URL` 与 `ZHIJING_PYTHON_URL`。

## 验收命令

```powershell
uv run --locked --no-sync pytest -q
uv run --locked --no-sync python dev/verify_contract.py compare
uv run --locked --no-sync python dev/verify_contract.py python
# Vite 回切 Spring 后执行
uv run --locked --no-sync python dev/verify_contract.py spring
```

实时超时测试使用单独的 FastAPI 实例。在模拟模型已启动、模型环境已配置的情况下，用单独终端启动该实例，再运行 `uv run --locked --no-sync python dev/verify_contract.py timeout`。

```powershell
$env:ZHIJING_AI_ROUND_TIMEOUT = '0.3'
$env:ZHIJING_AI_MIN_CHUNK_TIME = '0'
uv run --locked --no-sync uvicorn zhijing.main:app --app-dir backend --host 127.0.0.1 --port 18083
```

退出上述终端会话即可清除该会话的预算覆盖。

浏览器验收使用真实 Vue 编辑器和笔记 API。安装 Playwright 后，在对应的 Vite 路由模式下运行命令。已有 Chromium 时可以设置 `ZHIJING_CHROMIUM_PATH` 指向可执行文件。

```powershell
uv pip install --target .dev/browser-deps playwright==1.65.2
$env:PYTHONPATH = (Resolve-Path .dev/browser-deps).Path
uv run --locked --no-sync python -m playwright install chromium
uv run --locked --no-sync python dev/verify_editor.py python
# Vite 回切 Spring 后执行
uv run --locked --no-sync python dev/verify_editor.py spring
```

## 第一阶段验收记录

- Python 测试通过 23 项。用 0.3 秒预算的独立 FastAPI 实例实测超时，依次收到开始进度、分段进度和 `failed`。
- 对照 Spring Boot 与 FastAPI 的 16 组请求，HTTP 状态、媒体类型、JSON 或 SSE 事件负载一致。另测语法损坏的 JSON，HTTP 500 和错误结构一致，`msg` 的解析诊断由各自框架生成。
- 同一组合成 Markdown 经 Vite 发给 Python 时，首个进度在约 0.01 秒内抵达，约 8.06 秒后完成。原端口回切 Spring 后复测同一正文，约 0.03 秒收到进度，约 8.03 秒完成。模拟模型记录与路由一致。
- Chromium 中通过润色和整理格式、候选预览、替换正文及显式保存。取消会关闭上游请求。处理期间用浏览器后退切换笔记时，基线界面仍可显示旧预览，应用操作被拒绝，另一篇笔记的未保存草稿保留。回切 Spring 后再次通过润色和保存。
- 本次使用模拟模型与独立 MySQL 9.7 实例。尚未验证真实模型服务、Spring 默认 270 秒超时以及生产代理。

项目约定与两份 Markdown 技能来自 LearnHub `767b4aa`。相关材料适用 [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)。

Required Notice: Copyright (c) 2026 QiuLf
