"""
本日志文件代码设计策略：
把python标准库logging等第三方库的日志，全部转发到loguru,
Loguru用作将不同库的不同格式日志进行格式统一
"""

import logging
import sys
from loguru import logger

from eduquery.core.config import settings


class InterceptHandler(logging.Handler):
    """
    把标准库的logging(uvicorn/sqlalchemy)的日志转发给loguru
    """
    def emit(self, record:logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame,depth = logging.currentframe(),2
        while frame and frame.f_code.co_filename ==logging.__file__:
            frame = frame.f_back
            depth+=1
        logger.opt(depth=depth,exception=record.exc_info).log(level,record.getMessage())

def setup_logging()->None:
    """
    定义设置日志记录器函数，为每个框架设置自己的日志记录器
    """
    settings.LOG_DIR.mkdir(parents=True,exist_ok=True)
    logger.remove()
    fmt=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    logger.add(sys.stderr, level=settings.LOG_LEVEL, format=fmt, enqueue=True)
    logger.add(
        settings.LOG_DIR / "app_{time:YYYY-MM-DD}.log",
        level=settings.LOG_LEVEL,
        format=fmt,
        rotation="00:00",
        retention="14 days",
        encoding="utf-8",
        enqueue=True
    )
    logger.add(
        settings.LOG_DIR / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format=fmt,
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        backtrace=True,
        diagnose=settings.DEBUG,
        enqueue=True
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        lg = logging.getLogger(name)
        lg.handlers = [InterceptHandler()]
        lg.propagate = False

