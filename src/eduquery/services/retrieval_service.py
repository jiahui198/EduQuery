"""
检索召回功能，并将召回的内容进行拼接
"""
from loguru import logger

# 向量数据库基本API
from eduquery.rag import vectorstore as vs
from eduquery.rag.embedder import embed_query


async def retriever(question: str, top_k: int = 5) -> list[dict]:
    """
    定义检索功能

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









