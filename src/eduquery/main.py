import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from eduquery.core.logging import setup_logging
from loguru import logger
from eduquery.core.config import settings
from eduquery.api.v1 import health,auth,chat,conversations,admin
from fastapi.middleware.cors import CORSMiddleware

from eduquery.core.db import init_db,close_db
from eduquery.core.redis import get_redis,close_redis
from eduquery.rag.vectorstore import  ensure_collection

from eduquery.core.exceptions import register_exception_handlers


#前端静态页面目录：项目根目录下的 frontend/（与 src 同级）
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app:FastAPI):
    """
    异步上下文管理器，
    用来向控制面板终端输出运行信息；
    用来管理mysql,redis的连接和关闭；
    """
    setup_logging()
    logger.info("{}启动 | env={} debug={}",settings.APP_NAME,settings.APP_ENV,settings.DEBUG)
    try:
        await init_db()                             #创建数据库
        await asyncio.to_thread(ensure_collection)  #创建向量集合
        await get_redis().ping()                    #建立redis客户端并ping探活
    except Exception as exc:
        logger.exception("依赖初始化失败：{}",exc)
        raise
    logger.info("MySQL/Redis连接就绪")

    yield

    await close_db()
    await close_redis()
    logger.info("{}已关闭",settings.APP_NAME)


def create_app()->FastAPI:
    app = FastAPI(
        title=f"{settings.APP_NAME}API",
        description="高校知识库问答系统",
        debug=settings.DEBUG,
        lifespan=lifespan
    )
    #添加跨域中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins = ["*"] if settings.DEBUG else ["https://your-domain.com"],
        allow_credentials=True,     #允许携带cookie,token
        allow_methods = ["*"],      #允许所有请求方法
        allow_headers = ["*"]       #允许所有请求头
    )
    #将所有异常捕获handler添加到app
    register_exception_handlers(app)

    app.include_router(health.router,prefix=settings.API_V1_PREFIX,tags=["health"])
    app.include_router(auth.router,prefix=settings.API_V1_PREFIX)
    app.include_router(chat.router,prefix=settings.API_V1_PREFIX)
    app.include_router(conversations.router,prefix=settings.API_V1_PREFIX)
    app.include_router(admin.router,prefix=settings.API_V1_PREFIX)

    #挂载前端页面，访问 http://127.0.0.1:8000/ 即可打开
    #注意：必须放在所有 API 路由之后，否则 "/" 会把 /api/v1 一起吃掉
    if FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app

app = create_app()










