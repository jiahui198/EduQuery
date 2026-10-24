"""
本模块主要用来定义所用模型（即文本模型和向量模型），集中管理集中控制
"""
from functools import lru_cache

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_openai import ChatOpenAI
from loguru import logger

from eduquery.core.config import settings


@lru_cache
def get_embedding_model()->DashScopeEmbeddings:
    """
    定义向量embedding模型，运行后返回向量模型单例
    """
    logger.info("初始化向量模型：{}",settings.EMBEDDING_MODEL)
    return DashScopeEmbeddings(
        model=settings.EMBEDDING_MODEL,
        dashscope_api_key=settings.DASHSCOPE_API_KEY
    )

@lru_cache
def get_chat_model(temperature:float=0.3)->ChatOpenAI:
    """
    定义对话模型，使用ChatOpenAI兼容接口
    :param temperature:温度控制默认0.3
    :return:dashscope模型
    """
    logger.info("初始化llm:{},temperature{}",settings.LLM_MODEL,temperature)
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,
        temperature=temperature,
        timeout=60.0,
        max_retries=2
    )












