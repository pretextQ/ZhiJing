# 知径后端迁移计划

> 历史试点计划。第 1、2 节已完成验收。知径现作为独立的 Python 个人学习工作台开发，请从 [项目 README](README.md) 启动。

知径是 LearnHub 的后续项目，定位为个人知识工作台。新仓库是 `https://github.com/pretextQ/ZhiJing.git`，本地目录是 `D:\projects\ZhiJing`。对照项目在 `D:\projects\LearnHub`，编写计划时其 HEAD 为 `767b4aa`。以该版本的接口、前端和测试记录迁移基线。

目标是把主后端逐步迁到 FastAPI。第一阶段交付一个能从现有 Vue 笔记编辑器操作的流式润色接口，后续按模块替换。首轮兼容方案沿用 MySQL、已有表结构、Flyway 迁移历史和上传文件布局。

## 1. 接入新仓库

- 检查 GitHub 仓库是否已有提交。以远端默认分支为基础开始，空仓库则初始化本地仓库并登记 `origin`。保留这份计划和远端已有文件。
- 在新仓库建立 FastAPI 项目和本地测试入口，使用 Pydantic 校验请求、HTTPX 调用模型、pytest 运行测试。依赖版本和启动方式写入仓库，模型地址、名称和密钥由环境变量提供。
- 把 LearnHub 中适用的 UI、笔记编辑、目录浏览、LaTeX 和合成数据约定带入新仓库。示例、测试和提交只用合成数据，模型密钥、上传资料、实例配置和数据库备份留在仓库外。

## 2. 用流式润色验证第一条链路

范围是 `POST /api/ai/polish-stream`。该接口接收正文并返回候选结果，保存仍由笔记编辑器发起。试点通过环境变量连接模型，可在没有数据库连接的环境中运行。用 Vite 或 nginx 只把这个路径指向 FastAPI，其余请求继续发给 Spring Boot。开发环境保留可切回 Spring Boot 的路由配置。

| 对照文件（相对于 LearnHub） | 核对内容 |
| --- | --- |
| `backend/src/main/java/org/dyh/learnhub/controller/AiController.java` | POST 请求、前置错误响应、SSE 的 `progress`、`done` 和 `failed` |
| `backend/src/main/java/org/dyh/learnhub/dto/AiPolishRequest.java` | 非空 `text`、`mode` 默认行为以及 `polish` 和 `format` 两种处理方式 |
| `backend/src/main/java/org/dyh/learnhub/ai/AgentService.java` | 技能提示词、长文分片、模型时间预算、输出完整性和长度保护 |
| `frontend/src/api/index.js` 与 `frontend/src/views/NoteEdit.vue` | SSE 解析、进度展示、取消、预览、保存和当前草稿归属 |
| `skills/markdown-polish/` 与 `skills/markdown-beautify/` | 润色和整理格式的现有行为 |

### 第一阶段验收

- 用同一组合成请求对比 Java 与 Python 的状态码、JSON 错误结构和 SSE 事件顺序及字段。现有 `streamPost` 按 `\n\n` 分帧，验证 FastAPI 经代理发送的实际字节和实时进度。
- 用模拟模型覆盖正常润色、整理格式、空正文、超时、响应截断和输出明显缩水。用含表格、代码围栏和多行 LaTeX 的长笔记验证分片和拼接结果。
- 在现有 Vue 编辑器操作两种模式，验证进度在请求结束前到达、取消和切换笔记时旧结果无法覆盖当前草稿、确认和保存仍按编辑器流程执行。
- 在同一套开发环境把 API 路由切回 Spring Boot，用同一份合成笔记确认功能可恢复。记录启动、测试和切回命令。完成这些验收后再扩展迁移范围。

## 3. 按模块迁移，逐块验收

1. **笔记与目录。** 对齐笔记读写、版本冲突、标签和分类关联、文件夹导航与分页。先从读取接口验证数据库映射，再迁写入。按模块指定写入服务，避免两套后端同时修改同一业务数据。
2. **资料库与检索。** 对齐上传下载、已有文件路径、目录和分页、抽文、OCR、切块及向量索引维护。用合成资料验证老数据读取、失败重试、重复任务和删除后的索引清理。默认 MySQL 检索与启用 Milvus 的配置各自验收。
3. **智能体与知识工作流。** 迁移会话、工具确认、RAG、Wiki 和知识图谱。核对聊天 SSE 事件、取消、会话和笔记作用域、引用追溯。用现有评测脚本和合成数据对比检索结果并验证关键编辑流程。
4. **发布与切换。** 对齐 Compose 健康检查、npx 安装更新及恢复、MCP API 和 Windows 启动器本地模式。验证全新安装，以及从 LearnHub 旧结构升级并打开原有笔记和附件。任何需要改变表结构的步骤都要明确迁移执行方，并在独立测试实例演练升级和恢复。涉及 DDL 时，回退演练包含数据库、上传文件和旧版本应用的配套恢复。

## 给新会话的启动指令

> 在 `D:\projects\ZhiJing` 工作，按 `MIGRATION_PLAN.md` 执行第 1、2 节。以 `D:\projects\LearnHub` 的 `767b4aa` 为对照，先跑通流式润色以及前端与代理验收，用合成数据和模拟模型覆盖回归。完成后汇报运行方式、验证结果和还未验证的环境，再决定下一批模块。
