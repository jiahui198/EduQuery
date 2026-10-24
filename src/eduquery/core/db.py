from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker,create_async_engine
from eduquery.core.config import settings

engine = create_async_engine(
    settings.mysql_dsn,
    echo = settings.MYSQL_ECHO,         #不打印数据库日志
    pool_pre_ping =True,                #在取连接前先测试ping
    pool_recycle=3600,                  #一小时回收连接
    pool_size=settings.MYSQL_POOL_SIZE,  #最大连接池大小
    max_overflow=settings.MYSQL_MAX_OVERFLOW
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,     #提交之后，不会将提交对象设置过期
    autoflush=False             #关闭查询时之前自动flush,精确手动控制
)


async def get_db()->AsyncGenerator[AsyncSession,None]:
    """
    FastAPI依赖注入时用：每次请求自动创建session,用完自动关闭
    返回：
        AsyncGenerator(AsyncSession),异步连接对象
    关闭：
        当路由函数使用完session执行完数据库操作后调用session.close
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()    #事务回滚
            raise                       #向上抛出交给FastAPI异常处理
        finally:
            await session.close()

async def init_db()->None:
    """
    创建启动时异步创建定义的所有表的函数（幂等，已存在则跳过）
    """
    from eduquery.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db()->None:
    """
    优雅停机，FastAPI服务关停时将彻底关闭连接池
    """
    await engine.dispose()
    logger.info("MySQL连接池已释放")