"""
检索召回功能，并将召回的内容进行拼接
"""
from loguru import logger

from eduquery.core.config import settings
# 向量数据库基本API
from eduquery.rag import vectorstore as vs
from eduquery.rag.embedder import embed_query
from eduquery.rag import retrievers


async def retriever(question: str, top_k: int = 5) -> list[dict]:
    """
    定义基础的检索功能（不含召回+精排）

    :param question: 用户问题
    :param top_k: 返回结果数量
    :return:检索结果字典列表
    """
    if not question.strip():
        return []

    vector = await embed_query(question)
    hits = vs.search(query_vector=vector,top_k=top_k)
    logger.info("召回{}条|最高分{:.3f}",len(hits),hits[0]["score"] if hits else 0.0)
    return hits


async def hybrid_retriever(question:str,top_k:int=5)->list[dict]:
    """
    混合检索+重排：BM25 + 向量 → RRF 融合 → gte-rerank 精排
    返回 build_context 能吃的 dict 列表（score 已经是 rerank 相关度，不再是余弦值）

    :param question: 用户问题
    :param top_k: 最终保留条数
    :return: 检索结果字典列表
    """
    if not question.strip():
        return []

    ret = await retrievers.get_retriever()
    if ret is None:
        return []

    # 检索链是同步实现，ainvoke 会把它丢进线程池，不阻塞事件循环
    docs = await ret.ainvoke(question)

    hits = [
        {
            "text": d.page_content,
            "title": d.metadata.get("title", ""),
            "source_url": d.metadata.get("source_url"),
            "doc_id": d.metadata.get("doc_id"),
            "score": float(d.metadata.get("relevance_score", 0.0)),
        }
        for d in docs
    ]
    # rerank 分低于阈值的都是噪声：知识库外的问题实测只有 0.006，相关内容 0.16 以上
    kept = [h for h in hits if h["score"] >= settings.RERANK_MIN_SCORE]
    logger.info("混合+重排：粗召回 {} 条 → 过滤后 {} 条", len(docs), len(kept))
    return kept[:top_k]



def build_context(hits:list[dict])->tuple[str,list[dict]]:
    """
    把召回结果编成带编号的上下文，同时抽出引用来源

    :param hits:检索结果列表
    :returns :返回拼接好喂给模型的文本 / 返回结结构化的输出结果
    """
    if not hits:
        return "",[]

    blocks,sources = [],[]
    for i,h in enumerate(hits,start=1):
        blocks.append(f"[{i}] 来源：{h['title']}\n{h['text']}")
        sources.append({
            "index":i,
            "title":h["title"],
            "source_url":h.get("source_url"),
            "doc_id":h.get("doc_id"),
            "score":round(float(h["score"]),4),
        })
    return "\n\n".join(blocks),sources









