"""
项目的配置文件:
    应用信息；
    日志；
    阿里百炼；
    mysql数据库；
    redis；
    milvus向量数据库；
"""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings,SettingsConfigDict
from typing import Literal

BASE_DIR = Path(__file__).resolve().parents[3]   #父目录

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR/".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    #----应用----
    APP_NAME:str = "EduQuery"
    APP_ENV :Literal["dev","prod"] = "dev"
    DEBUG:bool = True
    API_V1_PREFIX:str = "/api/v1"   #api版本前缀
    SECRET_KEY:str = "dev-only-change-me"

    #----日志----
    LOG_LEVEL:str = "INFO"
    LOG_DIR:Path = BASE_DIR/"logs"

    #----阿里模型配置----
    DASHSCOPE_API_KEY:str = ""
    DASHSCOPE_BASE_URL:str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL:str = "qwen-plus"
    EMBEDDING_MODEL:str = "text-embedding-v4"
    EMBEDDING_DIM:int = 1024

    #----MySQL----
    MYSQL_HOST :str = "127.0.0.1"
    MYSQL_PORT:int = 3306
    MYSQL_USER:str ="eduquery"
    MYSQL_PASSWORD:str = ""
    MYSQL_DATABASE:str = "eduquery"
    MYSQL_POOL_SIZE:int = 10        #连接池大小
    MYSQL_MAX_OVERFLOW:int=20       #连接池最大溢出数
    MYSQL_ECHO:bool = False         #不打印数据库日志

    #RAG检索配置
    RETRIEVE_K:int = 10         #每路粗召回条数
    RERANK_TOP_N:int = 4        #重排后保留条数
    BM25_WEIGHT:float = 0.5     #关键词检索（稀疏检索）权重
    DENSE_WEIGHT:float = 0.5    #向量检索（稠密检索）权重
    RRF_C:int = 60              #RRF平滑常数
    RERANK_MIN_SCORE:float = 0.05

    @property
    def mysql_dsn(self)->str:
        return(
            f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    #----Redis----
    REDIS_HOST:str = "127.0.0.1"
    REDIS_PORT:int = 6379
    REDIS_DB :int = 0
    REDIS_PASSWORD:str =""
    REDIS_POOL_SIZE:int =20

    #----Milvus----
    MILVUS_URI:str = str(BASE_DIR/"data"/"milvus_eduquery.db")
    MILVUS_TOKEN:str = ""
    MILVUS_COLLECTION:str = "edu_knowledge"

    #JWT鉴权
    JWT_SECRET:str = "please_change_me" #secret
    JWT_ALGORITHM:str = "HS256"         #鉴权算法
    JWT_EXPIRE_MINUTES:int=1440         #token有效时间为24小时

@lru_cache
def get_settings()->Settings:
    return Settings()

settings = get_settings()







