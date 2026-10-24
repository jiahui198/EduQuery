from functools import lru_cache
import redis.asyncio as aioredis
from eduquery.core.config import settings
from loguru import logger

@lru_cache
def get_redis()->aioredis.Redis:
    """
    返回一个Redis客户端（单例）
     显示创建连接池：
                max_connections      最大连接数
                decode_response=True 返回值时str不用手动解析
    """
    pool = aioredis.ConnectionPool(
        host = settings.REDIS_HOST,
        port = settings.REDIS_PORT,
        password = settings.REDIS_PASSWORD or None,
        db = settings.REDIS_DB,     #连接的数据库序号0
        max_connections=settings.REDIS_POOL_SIZE,
        decode_responses = True,
        health_check_interval=30,   #每30秒进行健康检查
    )
    return aioredis.Redis(connection_pool=pool)


async def close_redis()->None:
    """
    FastAPI服务器关停时优雅停机，关闭与redis的理解
    """
    await get_redis().aclose()
    logger.info("Redis连接池已释放")

