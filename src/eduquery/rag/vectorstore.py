"""
本模块用于设计我们对milvus向量数据库的设计：
    向量数据库milvus集合的构建
    向量数据库集合字段添加索引
    向向量数据库插入数据函数API；
    为向量数据库设计查询函数API
    定义按照文档删除的函数API
"""
from functools import lru_cache

from loguru import logger
from pymilvus import MilvusClient,DataType
from eduquery.core.config import settings


@lru_cache
def get_milvus()->MilvusClient:
    """
    设计Milvus连接客户端单例，后续若使用server版只在config中改动uri
    """
    return MilvusClient(uri=str(settings.MILVUS_URI))


def ensure_collection()->None:
    """
    定义创建结合，集合存在则跳过，不存在就创建集合
    """
    client = get_milvus()
    name = settings.MILVUS_COLLECTION

    if client.has_collection(collection_name=settings.MILVUS_COLLECTION):
        return

    schema = client.create_schema(auto_id=True,enable_dynamic_field=False)

    schema.add_field("id",DataType.INT64,is_primary=True)
    schema.add_field("vector",DataType.FLOAT_VECTOR,dim=settings.EMBEDDING_DIM)
    schema.add_field("doc_id",DataType.INT64)
    schema.add_field("chunk_index",DataType.INT64)
    schema.add_field("text",DataType.VARCHAR,max_length=4096)
    schema.add_field("title",DataType.VARCHAR,max_length=512)
    schema.add_field("source_url",DataType.VARCHAR,max_length=1024)

    #为我们的vector稠密向量字段添加索引
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="AUTOINDEX",     #索引类型为AUTOINDEX
        metric_type="COSINE"        #使用COSINE余弦相似度
    )
    client.create_collection(
        collection_name=settings.MILVUS_COLLECTION,
        schema=schema,
        index_params=index_params
    )

def insert_chunks(rows:list[dict])->list[int]:
    """
    定义向向量数据库中插入元素函数
    :param rows:字典列表
    :return:主键列表
    """
    if not rows:
        return []
    #.insert返回:
    #{
    #    "insert_count": 3,  # 成功插入多少条
    #    "ids": [10001, 10002, 10003],  # Milvus自动生成的主键id列表
    #    "cost": 0
    #}

    return get_milvus().insert(settings.MILVUS_COLLECTION,rows)["ids"]


def delete_by_doc(doc_id:int)->None:
    """
    定义按照文档id删除向量数据库文档函数
    :param doc_id: 文档id
    """
    get_milvus().delete(settings.MILVUS_COLLECTION,filter=f"doc_id=={doc_id}")


def search(query_vector:list[float],top_k:int=5)->list[dict]:
    """
    相似度搜索,可一次传入多个搜索问题
    :param query_vector:查询向量
    :param top_k: 返回结果数量
    :return: list[dict]
    """
    hits = get_milvus().search(
        settings.MILVUS_COLLECTION,
        [query_vector],
        limit=top_k,
        output_fields=["doc_id","chunk_index","text","title","source_url"]
    )
    #返回字典列表形式的相似度得分和output_fields字段
    return [{"score":h["distance"],**h["entity"]} for h in hits[0]]












