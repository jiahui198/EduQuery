# 项目长期约定 — EduQuery（高校知识库问答系统）

## 基本信息
- 需求文档（资料库）：https://www.workbuddy.cn/space/d/1KFosYOvJRMqNMEtwDTBW0
- 代码仓库：D:\python_practice\EduQuery（uv，python 3.11，src 布局）
- 用户：大四学生 / Python 工程师，已学 langchain、langgraph、milvus、fastapi、pydantic、mysql、redis
- 参考项目：D:\python_practice\question_response_agent（他自建的 FastAPI+LangGraph 项目，结构与 MySQL/Redis 写法可复用）

## 协作方式（重要）
- **用户全程自己敲（红线）**：目录、依赖、每个代码文件都由他写；我只给「下一步 + 参考代码 + 命令」、做 code review、跑验证、讲坑。
  **不得直接用 Write/Edit 写入 `D:\python_practice\EduQuery` 下的工程文件**（2026-10-27 因此被要求全部回退）。
  唯一例外：用户当场明确说「你来写/帮我生成代码文件」。
- 不一次性给全量代码，每阶段 2~4 个文件；每阶段必须实测跑通再继续。
- **回复要精简**（用户多次要求压缩上下文）。
- **不要在主线推进过程中回头重提小的优化/重构**（2026-10-29 用户明确表达"思路很乱"）。
  如 `deps.py` 换 HTTPBearer、`ApiResponse` 信封、抽 `_resolve_user` 这类锦上添花的改动，
  最多提一次并标注「非阻塞」，用户没主动接话就彻底搁置，等主线走完再说。

## 技术选型
- LLM/Embedding：阿里百炼 DashScope。LLM=qwen-plus（ChatOpenAI + base_url 兼容模式），Embedding=text-embedding-v4（dim 1024，实测确认）
- 向量库：Milvus Lite（./data/milvus_eduquery.db），后期换阿里云服务器只改 MILVUS_URI
- 业务库：本地 MySQL80（eduquery 用户/库，非 Docker）；Redis 用本机 Memurai（6379，无密码）
- 前端：FastAPI + Jinja2 + 原生 JS；可观测：loguru + Langfuse（阶段7）；评估：ragas
- PyPI 走阿里云镜像（全局配置 C:\Users\13564\AppData\Roaming\uv\uv.toml；清华源会 403）

## 架构约定
- **异常兜底（用户明确要求）**：业务层只 `raise` 自定义异常，不在接口里 try/except；
  统一错误响应体 `{code, message, detail, request_id}`；
  异常体系在 `core/exceptions.py`（BizException 基类 + AuthError/TokenExpiredError/NotFoundError/
  PermissionDeniedError/ConflictError/ExternalServiceError(LLM/VectorStore/DB/Cache)/IngestError）；
  main.py 注册 4 个 handler（Biz / StarletteHTTP / RequestValidationError / 兜底 Exception）；
  `core/middleware.py` 的 RequestContextMiddleware 用 contextvar 生成并透传 X-Request-ID，供日志串联
  （2026-10-27 曾一次性写入后被用户要求全部回退，**方案保留、代码待他手敲落地**）
- 模型对象统一在 `core/llm.py` 定义（get_embedding_model / get_chat_model，lru_cache 单例）；业务模块只调用，不自定义模型
- **成功响应体暂不统一（2026-10-28 用户决策）**：先把 auth 等接口跑通，之后再批量套 `ApiResponse`。
  届时每个路由的改动量 = 加 `response_model=ApiResponse[XxxOut]` + return 改成 `ApiResponse(data=...)`。
  ⚠️ 但**输出模型（`schemas/auth.py` 的 StudentOut/AdminOut）不许推迟**——它防的是
  `hashed_password` 泄漏，属安全问题；信封只是格式整齐问题，二者不是一个优先级
- ORM 表在 `models/`（base/knowledge/user）；切分用 LangChain，落库转 ORM + Milvus row
- 上传文档（阶段5）走统一 `RawDoc` 结构，与网页共用同一条流水线

## 阶段 2 数据来源（官网已探明）
- 郑州工业应用技术学院 https://www.zzuit.edu.cn/ ，静态 HTML、utf-8、无反爬
- 列表页 index/tzgg.htm，约 10 条/页；文章 `/info/<栏目ID>/<文章ID>.htm`（通知公告=1120）
- 正文容器 `div.n_nry_main`（不能用 "con" 模糊匹配，会命中 n_container 导航）
- 噪声行「发布人：发布日期：…已有人浏览」会被 get_text 拆行 → 清洗须在整段文本上做 + `_flex` 允许字间空白
- embedding 单次请求上限 10 条（超了 400）；DashScopeEmbeddings 会自动分批，OpenAIEmbeddings 不会

## 本地开发账号（2026-10-29 建，仅本地用）
- 管理员：username=`admin` / password=`Admin@2026`（admins 表 id=5，由外部脚本幂等重建：
  `D:\tools\2026-10-22-18-08-55\verify_admin_path.py`）
- 学生：任意学号自行注册即可（注册接口目前完全公开，为已知待办）

## 已踩过的坑（供后续排查）
- pydantic 注解用冒号不是等号；REDIS_PORT 类型写错会让 Settings 校验失败
- sqlalchemy 需装 `sqlalchemy[asyncio]`（greenlet）；MySQL8 还需 cryptography
- redis-py 8 参数是 decode_responses（复数）
- milvus-lite 要直接 `uv add milvus-lite`（extra 写法不生效）；create_index 必须带 index_type='AUTOINDEX'

## 路线图与进度
0 骨架 ✅ → 1 MySQL+Redis 生命周期 ✅（4 张表：knowledge_doc/knowledge_chunk/students/admins）
→ 2 知识库流水线：fetcher+cleaner ✅ 实测通过；splitter/embedder/vectorstore + core/llm.py 已给（待用户敲完验证）
→ 3 混合检索+Rerank+RAG → 4 LangGraph Agent（动态工具/动态提示词/异常边界/长短记忆/上下文压缩/对话列表）
→ 5 管理端上传 → 6 定时任务 → 7 Langfuse+ragas → 8 部署

## 用户追加需求（并入阶段 4）
长期记忆（跨会话）、上下文压缩、展示对话列表 → 需提前补 conversations/messages 表
