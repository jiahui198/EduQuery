"""
本模块用于设计rag系统中的BM25稀疏检索+稠密检索（即混合检索）+重排
    build_hybrid_retriever()        → BM25 + 向量 + RRF 融合 :粗排
    build_rerank()                  → gte-rerank-v2 重排器  :精排
    builder_retriever_with_rerank() → 召回 + 精排一体化
"""
import dashscope
from loguru import logger

from eduquery.core.config import settings
import asyncio

import jieba
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_compressors import DashScopeRerank
from langchain_classic.retrievers import (
EnsembleRetriever,              #混合检索器
ContextualCompressionRetriever  #检索+精排检索器
)
from eduquery.core.db import async_sessionmaker
from sqlalchemy import select
from eduquery.models.knowledge import  (
KnowledgeDoc,
KnowledgeChunk
)
from eduquery.rag.embedder import embed_query
from eduquery.rag import vectorstore as vs


RERANK_MODEL = "gte-rerank-v2"
_retriever = None


async def _load_documents()->list[Document]:
    """
    将mysql数据库中存储的文档转换为Document对象并附加元数据doc_id/chunk_index等
    :return: Document对象列表
    """
    async with async_sessionmaker() as session:
        rows = (await session.execute(
            select(KnowledgeChunk.doc_id,KnowledgeChunk.chunk_index,KnowledgeChunk.content,
                   KnowledgeDoc.title,KnowledgeDoc.source_url)
            .join(KnowledgeDoc,KnowledgeDoc.id==KnowledgeChunk.doc_id)
        )).all()
    return [
        Document(page_content=r.content,
                 metadata={
            "doc_id":r.doc_id,"chunk_index":r.chunk_index,
            "title":r.title,"source_url":r.source_url
        })
    for r in rows]


def _jieba_tokenize(text:str)->list[str]:
    """
    定义中文切词函数
    :param text: 传入的中文文本
    :return: 切分后的文本列表
    """
    return list(jieba.cut(text))


class MilvusRetriever(BaseRetriever):
    """
    定义稠密向量检索器：
    继承BaseRetriever,因为我们使用的是Milvus原生的search检索方式，
    使用混合检索langchain-EnsembleRetriever,必须将原生的search封装成langchain检索器的形式
    """
    top_k: int = settings.RETRIEVE_K

    async def _aget_relevant_documents(
        self, query: str, **kwargs
    ) -> list[Document]:
        """
        覆写检索方法，接收一个字符串类型的查询query,并返回一个document对象列表
        :param query:用户查询语句
        :return:document对象列表
        """

        vector = await embed_query(text=query)
        hits = await asyncio.to_thread(vs.search,query_vector=vector,top_k=self.top_k)
        return [
            Document(
                page_content=h["text"],
                metadata={
                    "doc_id":h["doc_id"],"chunk_index":h["chunk_index"],
                    "title":h["title"],"source_url":h.get("source_url")
                }
            )
            for h in hits
        ]

def build_hybrid_retriever(
        chunks:list[Document],
        weights:list[float] | None=None,
        k:int|None = None
)->EnsembleRetriever:
    """
    定义混合检索器，稠密向量检索器+稀疏向量检索器+RRF
    :param chunks:list[Document]
    :param weights:权重
    :param k:单个检索器返回结果数量
    :return:混合检索器
    """
    if weights is None:
        weights = [0.5,0.5]

    if k is None:
        k= settings.RETRIEVE_K

    #bm25稀疏向量检索器
    bm25 = BM25Retriever.from_documents(
        chunks,
        preprocess_func=_jieba_tokenize
    )
    bm25.k = k

    return EnsembleRetriever(
        retrievers = [bm25,MilvusRetriever(top_k=k)],
        weights=weights,
        c = settings.RRF_C
    )


def build_rerank(top_n:int|None=None)->DashScopeRerank:
    """
    构建重排器实例
    :param top_n:精排后的返回结果条数
    :return: DashScopeRerank
    """
    if top_n is None:
        top_n = settings.RERANK_TOP_N

    return DashScopeRerank(
        client=dashscope.TextReRank,
        model = RERANK_MODEL,
        dascscope_api_key = settings.DASHSCOPE_API_KEY,
        top_n = top_n
    )


def builder_retriever_with_rerank(
    base_retriever:EnsembleRetriever,top_n:int|None = None
)->ContextualCompressionRetriever:
    return ContextualCompressionRetriever(
        base_retriever = base_retriever,
        base_compressor = build_rerank(top_n=top_n)
    )


async def rebuild_retriever() -> None:
    """对应 demo2 的 build_index()：重建单例。入库后必须调，否则新文章搜不到"""
    global _retriever
    chunks = await _load_documents()
    if not chunks:
        _retriever = None
        logger.warning("知识库为空，检索器未构建")
        return
    base = build_hybrid_retriever(chunks)
    _retriever = builder_retriever_with_rerank(base)
    logger.info("检索器已重建：{} 条切片", len(chunks))


async def get_retriever():
    """集成，所有知识库的加载和检索器的加载"""
    global _retriever
    if _retriever is None:
        await rebuild_retriever()
    return _retriever









