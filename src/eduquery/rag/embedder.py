"""
本模块将设计：
    对于爬取到的文本数据进行向量化的函数API
    对于我们的查询文本进行向量化的函数API
"""

import asyncio
from eduquery.core.llm import get_embedding_model

BATCH_SIZE=10


async def embed_texts(texts:list[str])->list[list[float]]:
    """
    将提取到的文本进行向量化

    :param texts: 提取到的文本列表
    :return: 二维向量浮点数
    """
    if not texts:
        return []

    embed_model = get_embedding_model()
    vectors:list[list[float]] = []

    for start in range(0,len(texts),BATCH_SIZE):
        batch = texts[start:start+BATCH_SIZE]
        vectors.extend(await asyncio.to_thread(embed_model.embed_documents,batch))
    return vectors


async def embed_query(text:str)->list[float]:
    """
    向量检索，将查询文本进行向量化

    :param text:查询文本
    :return: 向量化额查询文本
    """
    embed_model=get_embedding_model()
    return await asyncio.to_thread(embed_model.embed_query,text)









