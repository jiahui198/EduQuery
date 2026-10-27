import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from eduquery.core.logging import setup_logging
from loguru import logger
from eduquery.core.config import settings
from eduquery.api.v1 import health
from fastapi.middleware.cors import CORSMiddleware

from eduquery.core.db import init_db,close_db
from eduquery.core.redis import get_redis,close_redis
from eduquery.rag.vectorstore import  ensure_collection


@asynccontextmanager
async def lifespan(app:FastAPI):
    """
    异步上下文管理器，
    用来向控制面板终端输出运行信息；
    用来管理mysql,redis的连接和关闭；
    """
    setup_logging()
    logger.info("{}启动 | env={} debug={}",settings.APP_NAME,settings.APP_ENV,settings.DEBUG)

    await init_db()                             #创建数据库
    await asyncio.to_thread(ensure_collection)  #创建向量集合
    await get_redis().ping()                    #建立redis客户端并ping探活
    logger.info("MySQL/Redis连接就绪")

    yield

    await close_db()
    await close_redis()
    logger.info("{}已关闭",settings.APP_NAME)


def create_app()->FastAPI:
    app = FastAPI(
        title=f"{settings.APP_NAME}API",
        description="高校知识库问答系统",
        debug=True,
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
    app.include_router(health.router,prefix=settings.API_V1_PREFIX,tags=["health"])
    return app

app = create_app()







